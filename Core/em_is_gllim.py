"""Implements a crossed EM - GLLiM algorith to evaluate noise in model.
Diagonal covariance is assumed"""
import json
import logging
import multiprocessing
import time

import coloredlogs
import numba as nb
import numpy as np
from joblib import Parallel, delayed

import hapke.cython
from Core import cython
from Core.gllim import jGLLiM
from tools import context

# GLLiM parameters
Ntrain = 40000
K = 40
init_X_precision_factor = 10
maxIterGlliM = 100
stoppingRatioGLLiM = 0.005


N_sample_IS = 100000

INIT_COV_NOISE = 0.005  # initial noise
INIT_MEAN_NOISE = 0  # initial noise offset
maxIter = 100

NO_IS = False
"""If it's True, dont use Importance sampling"""

PARALLEL = True
"""Uses cython parallel version for mu step with IS"""

WITH_THREADS = True
"""Uses threading backend for joblib"""

N_JOBS = multiprocessing.cpu_count()

# ------------------------ Linear case ------------------------ #
@nb.njit(cache=True)
def _helper_mu_lin(y, F, K, inverse_current_cov, current_mean):
    return y - F.dot(K).dot(F.T).dot(inverse_current_cov).dot(y - current_mean)


@nb.njit(nogil=True, parallel=True, fastmath=True)
def _mu_step_lin(Yobs, F, prior_cov, current_mean, current_cov):
    Ny, D = Yobs.shape

    esp_mu = np.zeros((Ny, D))

    invsig = np.linalg.inv(current_cov)
    K = np.linalg.inv(np.linalg.inv(prior_cov) + F.T.dot(invsig).dot(F))

    for i in nb.prange(Ny):
        y = Yobs[i]
        esp_mu[i] = _helper_mu_lin(y, F, K, invsig, current_mean)
    maximal_mu = np.sum(esp_mu, axis=0) / Ny
    return maximal_mu, K, esp_mu


@nb.njit(nogil=True, parallel=True, fastmath=True)
def _mu_step_diag_lin(Yobs, F, prior_cov, current_mean, current_cov):
    Ny, D = Yobs.shape

    esp_mu = np.zeros((Ny, D))

    invsig = np.diag(1 / current_cov)
    K = np.linalg.inv(np.linalg.inv(prior_cov) + F.T.dot(invsig).dot(F))

    for i in nb.prange(Ny):
        y = Yobs[i]
        esp_mu[i] = _helper_mu_lin(y, F, K, invsig, current_mean)
    maximal_mu = np.sum(esp_mu, axis=0) / Ny
    return maximal_mu, K, esp_mu


@nb.njit(nogil=True, parallel=True, fastmath=True)
def _sigma_step_full_lin(F, K, esp_mu, max_mu):
    base_cov = F.dot(K).dot(F.T)
    Ny, D = esp_mu.shape
    esp_sigma = np.zeros((Ny, D, D))

    for i in nb.prange(Ny):
        u = max_mu - esp_mu[i]
        esp_sigma[i] = u.reshape((-1, 1)).dot(u.reshape((1, -1)))

    maximal_sigma = base_cov + (np.sum(esp_sigma, axis=0) / Ny)
    return maximal_sigma


@nb.njit(nogil=True, parallel=True, fastmath=True)
def _sigma_step_diag_lin(F, K, esp_mu, max_mu):
    base_cov = F.dot(K).dot(F.T)
    Ny, D = esp_mu.shape
    esp_sigma = np.zeros((Ny, D))

    for i in nb.prange(Ny):
        u = max_mu - esp_mu[i]
        esp_sigma[i] = np.square(u)

    maximal_sigma = np.diag(base_cov) + (np.sum(esp_sigma, axis=0) / Ny)
    return maximal_sigma


def _em_step_lin(F, Yobs, prior_cov, current_cov, current_mean):
    ti = time.time()

    _mu_step = _mu_step_diag_lin if current_cov.ndim == 1 else _mu_step_lin

    maximal_mu, K, esp_mu = _mu_step(Yobs, F, prior_cov, current_mean, current_cov)
    logging.debug(f"Noise mean estimation done in {time.time()-ti:.3f} s")

    ti = time.time()
    _sigma_step = _sigma_step_diag_lin if current_cov.ndim == 1 else _sigma_step_full_lin
    maximal_sigma = _sigma_step(F, K, esp_mu, maximal_mu)
    logging.debug(f"Noise covariance estimation done in {time.time()-ti:.3f} s")
    return maximal_mu, maximal_sigma


# -------------------------- General case -------------------------- #
def _init(cont: context.abstractHapkeModel):
    gllim = jGLLiM(K, sigma_type="full", verbose=False)
    Xtrain, Ytrain = cont.get_data_training(Ntrain)
    Ytrain = cont.add_noise_data(Ytrain, covariance=INIT_COV_NOISE, mean=INIT_MEAN_NOISE)  # 0 offset

    m = cont.get_X_uniform(K)
    rho = np.ones(gllim.K) / gllim.K
    precisions = init_X_precision_factor * np.array([np.eye(Xtrain.shape[1])] * gllim.K)
    rnk = gllim._T_GMM_init(Xtrain, 'random',
                            weights_init=rho, means_init=m, precisions_init=precisions)
    gllim.fit(Xtrain, Ytrain, {"rnk": rnk}, maxIter=1)
    return gllim.theta


def _gllim_step(cont: context.abstractHapkeModel, current_noise_cov, current_noise_mean, current_theta):
    ti = time.time()
    gllim = jGLLiM(K, sigma_type="full", stopping_ratio=stoppingRatioGLLiM)
    Xtrain, Ytrain = cont.get_data_training(Ntrain)

    Ytrain = cont.add_noise_data(Ytrain, covariance=current_noise_cov, mean=current_noise_mean)

    gllim.fit(Xtrain, Ytrain, current_theta, maxIter=maxIterGlliM)
    gllim.inversion()
    logging.debug(f"GLLiM step done in {time.time() -ti:.3f} s")
    return gllim


# ------------------- WITHOUT IS ------------------- #

def _em_step_NoIS(gllim, compute_Fs, get_X_mask, Yobs, current_cov, *args):
    Xs = gllim.predict_sample(Yobs, nb_per_Y=N_sample_IS)
    mask = get_X_mask(Xs)
    logging.debug(f"Average ratio of F-non-compatible samplings : {mask.sum(axis=1).mean() / N_sample_IS:.5f}")
    ti = time.time()

    FXs = compute_Fs(Xs, mask)
    logging.debug(f"Computation of F done in {time.time()-ti:.3f} s")
    ti = time.time()

    maximal_mu = cython.mu_step_NoIS(Yobs, FXs, mask)
    logging.debug(f"Noise mean estimation done in {time.time()-ti:.3f} s")

    ti = time.time()
    _sigma_step = cython.sigma_step_diag_NoIS if current_cov.ndim == 1 else cython.sigma_step_full_NoIS
    maximal_sigma = _sigma_step(Yobs, FXs, mask, maximal_mu)
    logging.debug(f"Noise covariance estimation done in {time.time()-ti:.3f} s")
    return maximal_mu, maximal_sigma


# --------------------------------- WITH IS --------------------------------- #

def mu_step_diag_IS_joblib(Yobs, Xs, meanss, weightss, FXs, mask, gllim_covs, current_mean, current_cov):
    Ny, Ns, D = FXs.shape
    K, L, _ = gllim_covs.shape
    gllim_chol_covs = np.zeros((K, L, L))
    for k in range(K):
        gllim_chol_covs[k] = np.linalg.cholesky(gllim_covs[k])

    maximal_mu = np.zeros(D)
    ws = np.zeros((Ny,Ns))

    prefer = "threads" if WITH_THREADS else None
    res = Parallel(n_jobs=N_JOBS, prefer=prefer)(delayed(cython.mu_step_diag_IS_i)(Yobs[i], Xs[i], meanss[i], weightss[i], FXs[i],
                                            mask[i], current_mean, current_cov,
                                            gllim_chol_covs) for i in range(Ny))

    for i, (mui, wsi) in enumerate(res):  #réduction
        maximal_mu += mui
        ws[i] = wsi
    return maximal_mu / Ny, ws


def mu_step_full_IS_joblib(Yobs, Xs, meanss, weightss, FXs, mask, gllim_covs, current_mean, current_cov):
    Ny, Ns, D = FXs.shape
    K, L, _ = gllim_covs.shape
    gllim_chol_covs = np.zeros((K, L, L))
    for k in range(K):
        gllim_chol_covs[k] = np.linalg.cholesky(gllim_covs[k])
    current_cov_chol = np.linalg.cholesky(current_cov)

    maximal_mu = np.zeros(D)
    ws = np.zeros((Ny,Ns))

    prefer = "threads" if WITH_THREADS else None
    res = Parallel(n_jobs=N_JOBS, prefer=prefer)(delayed(cython.mu_step_full_IS_i)(Yobs[i], Xs[i], meanss[i], weightss[i], FXs[i],
                                            mask[i], current_mean, current_cov_chol,
                                            gllim_chol_covs) for i in range(Ny))

    for i, (mui, wsi) in enumerate(res):  #réduction
        maximal_mu += mui
        ws[i] = wsi
    return maximal_mu / Ny, ws


def _log_sample_size(ws):
    ws = np.copy(ws)
    mask = ~ np.isfinite(ws)
    ws[mask] = 0

    effective_sample_size = np.sum(ws, axis = 1) ** 2 / np.sum(np.square(ws), axis=1)
    logging.debug("Effective mean sample size : {:.1f} / {}".format(effective_sample_size.mean(),N_sample_IS))


def _em_step_IS(gllim, compute_Fs, get_X_mask, Yobs, current_cov, current_mean):
    Xs = gllim.predict_sample(Yobs, nb_per_Y=N_sample_IS)
    mask = get_X_mask(Xs)
    logging.debug(f"Average ratio of F-non-compatible samplings : {mask.sum(axis=1).mean() / N_sample_IS:.5f}")
    ti = time.time()

    meanss, weightss, _ = gllim._helper_forward_conditionnal_density(Yobs)
    gllim_covs = gllim.SigmakListS

    FXs = compute_Fs(Xs, mask)
    logging.debug(f"Computation of F done in {time.time()-ti:.3f} s")
    ti = time.time()

    assert np.isfinite(FXs).all()

    if current_cov.ndim == 1:
        maximal_mu, ws = mu_step_diag_IS_joblib(Yobs, Xs, meanss, weightss, FXs, mask, gllim_covs, current_mean,
                                                current_cov)
    else:
        maximal_mu, ws = mu_step_full_IS_joblib(Yobs, Xs, meanss, weightss, FXs, mask, gllim_covs, current_mean,
                                                current_cov)
    assert np.isfinite(maximal_mu).all()
    _log_sample_size(ws)

    logging.debug(f"Noise mean estimation done in {time.time()-ti:.3f} s")

    ti = time.time()
    _sigma_step = cython.sigma_step_diag_IS if current_cov.ndim == 1 else cython.sigma_step_full_IS
    maximal_sigma = _sigma_step(Yobs, FXs, ws, mask, maximal_mu)
    logging.debug(f"Noise covariance estimation done in {time.time()-ti:.3f} s")
    return maximal_mu, maximal_sigma


class NoiseEM:
    """Base class for noise estimation based on EM-like procedure"""

    cont: context.abstractHapkeModel

    def __init__(self, Yobs, cont, cov_type):
        self.Yobs = Yobs
        self.cont = cont
        self.cov_type = cov_type

    def get_X_mask(self, X):
        m = np.asarray(~ self.cont.is_X_valid(X), dtype=int)
        return m

    def compute_Fs(self, Xs, mask):
        D = self.cont.D
        N, Ns, _ = Xs.shape
        FXs = np.empty((N, Ns, D))
        F = self.cont.F
        for i, (X, mask_x) in enumerate(zip(Xs, mask)):
            FX = F(X)
            FX[mask_x == 1, :] = 0  # anyway, ws will be 0
            FXs[i] = FX
        return FXs

    def fast_compute_Hapke(self, Xs, mask):
        N, Ns, _ = Xs.shape
        partiel = np.arange(self.cont.L) if self.cont.partiel is None else self.cont.partiel
        if hasattr(self.cont, "HAPKE_VECT_PERMUTATION"):
            perm = np.array(self.cont.HAPKE_VECT_PERMUTATION)
        else:
            perm = np.arange(self.cont.L)
        args = (np.asarray(self.cont.geometries, dtype=np.double), Xs, mask,
                                              partiel, self.cont.DEFAULT_VALUES,
                                              self.cont.variables_lims[:, 0],
                                              self.cont.variables_range, perm)

        FXs = hapke.cython.compute_many_Hapke(*args)

        return FXs

    def _get_starting_logging(self):
        return f"""
        Covariance constraint : {self.cov_type}
        Nobs = {len(self.Yobs)} 
        Initial covariance noise : {INIT_COV_NOISE} 
        Initial mean noise : {INIT_MEAN_NOISE}
        """

    def _get_F(self):
        "Should return F information"
        raise NotImplementedError

    def _init_gllim(self):
        "Should return a gllim theta if needed"
        return

    def _gllim_step(self, current_noise_cov, current_noise_mean, current_theta):
        "Should return gllim"
        return

    def _get_em_step(self):
        "Choose which function to use for em_step"
        raise NotImplementedError

    def run(self):
        log = "Starting noise estimation with EM" + self._get_starting_logging()
        logging.info(log)
        Yobs = np.asarray(self.Yobs, dtype=float)
        F = self._get_F()
        em_step = self._get_em_step()

        current_theta = self._init_gllim()
        base_cov = np.eye(self.cont.D) if self.cov_type == "full" else np.ones(self.cont.D)
        current_noise_cov, current_noise_mean = INIT_COV_NOISE * base_cov, INIT_MEAN_NOISE * np.ones(self.cont.D)
        history = [(current_noise_mean.tolist(), current_noise_cov.tolist())]

        for current_iter in range(maxIter):
            gllim = self._gllim_step(current_noise_cov, current_noise_mean, current_theta)

            max_mu, max_sigma = em_step(gllim, F, self.get_X_mask, Yobs, current_noise_cov, current_noise_mean)

            log_sigma = max_sigma if self.cov_type == "diag" else np.diag(max_sigma)
            logging.info(f"""
        Iteration {current_iter+1}/{maxIter}. 
            New estimated OFFSET : {max_mu}
            New estimated COVARIANCE : {log_sigma}""")
            current_noise_cov, current_noise_mean = max_sigma, max_mu
            history.append((current_noise_mean.tolist(), current_noise_cov.tolist()))
        return history


class NoiseEMLinear(NoiseEM):

    def _get_starting_logging(self):
        s = super()._get_starting_logging()
        return " (Linear case)" + s

    def _get_F(self):
        return self.cont.F_matrix

    def _get_em_step(self):
        def em_step(gllim, F, func_mask, Yobs, current_noise_cov, current_noise_mean):
            return _em_step_lin(F, Yobs, self.cont.PRIOR_COV, current_noise_cov, current_noise_mean)

        return em_step


class NoiseEMGLLiM(NoiseEM):

    def _get_starting_logging(self):
        s = super()._get_starting_logging()
        return f" with GLLiM \n\tNSample = {N_sample_IS}" + s

    def _get_F(self):
        if isinstance(self.cont, context.abstractHapkeModel):
            logging.info("Using C computation of Hapke's ")
            return self.fast_compute_Hapke
        else:
            logging.info("Using generic Python computation of F")
            return self.compute_Fs

    def _init_gllim(self):
        return _init(self.cont)

    def _gllim_step(self, current_noise_cov, current_noise_mean, current_theta):
        return _gllim_step(self.cont, current_noise_cov, current_noise_mean, current_theta)

    def _get_em_step(self):
        return _em_step_NoIS


class NoiseEMISGLLiM(NoiseEMGLLiM):

    def _get_starting_logging(self):
        s = NoiseEM._get_starting_logging(self)
        return f" with IS-GLLiM \n\tNSampleIS = {N_sample_IS}" + s

    def _get_em_step(self):
        return _em_step_IS



def fit(Yobs, cont: context.abstractFunctionModel, cov_type="diag", assume_linear=False):
    Yobs = np.copy(Yobs, "C")  # to ensure Y is contiguous
    if assume_linear:
        fitter = NoiseEMLinear(Yobs, cont, cov_type)
    elif NO_IS:
        fitter = NoiseEMGLLiM(Yobs, cont, cov_type)
    else:
        fitter = NoiseEMISGLLiM(Yobs, cont, cov_type)
    return fitter.run()


# ------------------ maintenance purpose ------------------ #
def _profile():
    global maxIter, Nobs, N_sample_IS, INIT_COV_NOISE, NO_IS
    NO_IS = True
    maxIter = 1
    Nobs = 200
    N_sample_IS = 80000
    cont = context.LabContextOlivine(partiel=(0, 1, 2, 3))

    _, Yobs = cont.get_data_training(Nobs)
    Yobs = cont.add_noise_data(Yobs, covariance=0.005, mean=0.1)
    Yobs = np.copy(Yobs, "C")  # to ensure Y is contiguous

    fit(Yobs, cont, cov_type="diag")


def _debug():
    global maxIter, Nobs, N_sample_IS, INIT_COV_NOISE, NO_IS
    NO_IS = False
    maxIter = 20
    Nobs = 40
    N_sample_IS = 20
    # cont = context.LabContextOlivine(partiel=(0, 1, 2, 3))
    cont = context.LinearFunction()
    INIT_COV_NOISE = 0.005
    _, Yobs = cont.get_data_training(Nobs)
    Yobs = cont.add_noise_data(Yobs, covariance=0.05, mean=2)
    Yobs = np.copy(Yobs, "C")  # to ensure Y is contiguous

    fit(Yobs, cont, cov_type="full", assume_linear=False)



if __name__ == '__main__':
    coloredlogs.install(level=logging.DEBUG, fmt="%(module)s %(name)s %(asctime)s : %(levelname)s : %(message)s",
                        datefmt="%H:%M:%S")
    # _profile()
    _debug()
