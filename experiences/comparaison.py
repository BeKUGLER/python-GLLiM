"""Sums up several tests on different contexts. Runs tests and saves results in json File.
Then translates this file into latex table.
"""
import logging
import os
import subprocess
import time
import warnings
from datetime import timedelta

import coloredlogs
import jinja2
import numpy as np

from Core.dgllim import dGLLiM
from Core.gllim import GLLiM, jGLLiM, WrongContextError
from experiences import logistic
from hapke import relation_C
from tools import context
from tools.archive import Archive
from tools.experience import Experience

warnings.filterwarnings("ignore")

NOISE = 50

ALGOS_exps = [
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 1000, "N": 10000,
     "init_local": 200, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 100, "N": 70000,
     "init_local": 200, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.HapkeGonio1468_50, "partiel": (0, 1, 2, 3), "K": 100, "N": 70000,
     "init_local": None, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.HapkeGonio1468, "partiel": (0, 1, 2, 3), "K": 100, "N": 70000,
     "init_local": None, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.HapkeGonio1468, "partiel": (0, 1, 2, 3), "K": 100, "N": 70000,
     "init_local": None, "sigma_type": "iso", "gamma_type": "full"}
]


GENERATION_exps = [
    {"context": context.InjectiveFunction(4), "partiel": (0, 1, 2, 3), "K": 50, "N": 500,
     "init_local": None, "sigma_type": "iso", "gamma_type": "full"},
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": None, "sigma_type": "iso", "gamma_type": "full"},
]

DIMENSION_exps = [
    {"context": context.InjectiveFunction(1), "partiel": None, "K": 100, "N": 50000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.InjectiveFunction(3), "partiel": None, "K": 100, "N": 50000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.InjectiveFunction(5), "partiel": None, "K": 100, "N": 50000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.InjectiveFunction(7), "partiel": None, "K": 100, "N": 50000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"}
]

MODAL_exps = [
    {"context": context.WaveFunction, "partiel": None, "K": 100, "N": 1000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.InjectiveFunction(3), "partiel": None, "K": 100, "N": 10000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"}
]

LOGISTIQUE_exps = [
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": 200, "sigma_type": "full", "gamma_type": "full"},
    {"context": logistic.LogisticOlivineContext, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": 200, "sigma_type": "full", "gamma_type": "full"}
]

NOISES_exps = [
    {"context": context.WaveFunction, "partiel": None, "K": 100, "N": 5000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.InjectiveFunction(4), "partiel": None, "K": 100, "N": 5000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
]

LOCAL_exps = [
    {"context": context.WaveFunction, "partiel": None, "K": 100, "N": 5000,
     "init_local": "", "sigma_type": "full", "gamma_type": "full"},
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 100, "N": 10000,
     "init_local": "", "sigma_type": "full", "gamma_type": "full"},
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 1000, "N": 20000,
     "init_local": "", "sigma_type": "full", "gamma_type": "full"}
]

RELATIONC_exps = [
    {"context": context.HapkeContext, "partiel": (0, 1, 2, 3), "K": 100, "N": 50000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": relation_C.HapkeCRelationContext, "partiel": (0, 1, 2), "K": 100, "N": 50000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"}
]

PARCOMPONENTS_exps = [
    {"context": context.HapkeContext, "partiel": None, "K": 100, "N": 100000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.HapkeContext, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"}
]

CLUSTERED_PREDICTION_exps = [
    {"context": context.HapkeContext, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.TwoSolutionsFunction, "partiel": None, "K": 100, "N": 10000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
]


def pretty_time_delta(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return '{}j {}h {}m '.format(days, hours, minutes)
    elif hours > 0:
        return '{}h {}m '.format(hours, minutes)
    elif minutes > 0:
        return '{}m {}s'.format(minutes, seconds)
    else:
        return '{}s'.format(seconds)

def _load_train_gllim(i, gllim_cls, exp, exp_params, noise, method,
                      redata, retrain):
    logging.info("  Starting {name} (K = {K}, N = {N})  ...".format(name=gllim_cls.__name__, **exp_params))
    ti = time.time()
    try:
        exp.load_data(regenere_data=redata, with_noise=noise, N=exp_params["N"], method=method)
        rnk_init = exp_params.get("rnk_init", None)
        gllim, training_time = exp.load_model(exp_params["K"], mode=retrain and "r" or "l", rnk_init=rnk_init,
                                              init_local=exp_params["init_local"],
                                              sigma_type=exp_params["sigma_type"], gamma_type=exp_params["gamma_type"],
                                              gllim_cls=gllim_cls, with_time=True)
    except FileNotFoundError as e:
        logging.warning(
            "--- No model or data found for experience {}, version {} - noise : {} ---".format(i + 1,
                                                                                               gllim_cls.__name__,
                                                                                               noise))
        return {"__error__": "Données ou modèle indisponibles"}
    except WrongContextError as e:
        logging.warning("\t{} method is not appropriate for the parameters ! "
                        "Details \n\t{} \n\tIgnored".format(gllim_cls.__name__, e))
        return {"__error__": " Contraintes incompatibles "}
    except np.linalg.LinAlgError as e:
        logging.error("\tTraining failed ! {}".format(e))
        return {"__error__": "Instabilité numérique"}
    except MemoryError:
        logging.critical("\t Memory Error ! Training failed")
        return {"__error__": "Mémoire vive insuffisante"}
    except AssertionError as e:
        logging.error("\tTraining failed ! {}".format(e))
        return {"__error__": str(e)}
    logging.info("  Model fitted or loaded in {}".format(timedelta(seconds=time.time() - ti)))
    return gllim, training_time


def _load_train_measure_gllim(i, gllim_cls, exp, exp_params, noise, method,
                              redata, retrain, Xtest=None, Ytest=None):
    """If Xtest and Ytest are given, use instead of exp data.
    Useful to fix data across severals exp"""
    r = _load_train_gllim(i, gllim_cls, exp, exp_params, noise, method, redata, retrain)
    if type(r) is dict:
        return r
    gllim, training_time = r
    ti = time.time()
    if Xtest is not None:
        exp.Xtest, exp.Ytest = Xtest, Ytest
    else:
        exp.centre_data_test()
    m = exp.mesures.run_mesures(gllim)
    m["training_time"] = training_time
    logging.info("  Mesures done in {}".format(timedelta(seconds=time.time() - ti)))
    if "get_rnk_init" in exp_params:
        return m, gllim._rnk_init
    return m

class abstractMeasures():
    """Runs mesures on new trained or loaded gllims"""

    METHODES = []
    experiences = []

    @classmethod
    def run(cls,train=None,run_mesure=None):
        o = cls()
        o.mesure(train,run_mesure)

    def __init__(self):
        self.CATEGORIE = self.__class__.__name__

    def _get_train_measure_choice(self, train, run_mesure):
        imax = len(self.experiences)
        train = [train] * imax if type(train) is bool else (train or [False] * imax)
        run_mesure = [run_mesure] * imax if type(run_mesure) is bool else (run_mesure or [False] * imax)
        return train, run_mesure

    def mesure(self,train,run_mesure):
        ti = time.time()
        train, run_mesure = self._get_train_measure_choice(train, run_mesure)
        imax = len(train)
        mesures = []
        old_mesures = Archive.load_mesures(self.CATEGORIE)
        for i, exp_params, t, rm in zip(range(imax), self.experiences, train, run_mesure):
            if rm:
                logging.info(f"Tests {self.CATEGORIE}, exp. {i+1}/{imax}")
                exp = Experience(exp_params["context"], partiel=exp_params["partiel"], verbose=False)
                dGLLiM.dF_hook = exp.context.dF
                dic = self._dic_mesures(i,exp,exp_params,t)
                if not '__error__' in dic:
                    assert set(self.METHODES) <= set(dic.keys()), f"Missing measures for {self.CATEGORIE}"
            else:
                try:
                    dic = old_mesures[i]
                    logging.info("Loaded mesures for exp. {}/{}".format(i + 1, imax))
                except IndexError:
                    logging.info("No mesure for exp. {}/{} found".format(i + 1, imax))
                    dic = {"__error__": "Mesure non effectuée"}
            mesures.append(dic)
        Archive.save_mesures(mesures, self.CATEGORIE)
        logging.info("Study carried in {} \n".format(timedelta(seconds=time.time() - ti)))

    def _dic_mesures(self, i, exp: Experience, exp_params, t):
        return {}


class abstractLatexWriter:
    LATEX_BUILD_DIR = "/scratch/WORK/_LATEX"

    LATEX_EXPORT_PATH = None
    """where to export bare latex file """

    latex_jinja_env = jinja2.Environment(
        block_start_string='(#',
        block_end_string='#)',
        variable_start_string='(!',
        variable_end_string='!)',
        comment_start_string='\#{',
        comment_end_string='}',
        line_statement_prefix='%%',
        line_comment_prefix='%#',
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        loader=jinja2.FileSystemLoader("templates_latex")
    )
    latex_jinja_env.globals.update(zip=zip)
    latex_jinja_env.filters["timespent"] = lambda s: pretty_time_delta(s)
    latex_jinja_env.filters["truncate01"] = lambda f: 1 if f > 1 else (0 if f < 0 else f)
    latex_jinja_env.tests["float"] = lambda p: type(p) is float

    template = ""
    """latex template file"""

    @classmethod
    def render(cls, **kwargs):
        """Wrapper"""
        w = cls()
        w.render_pdf(**kwargs)

    def __init__(self):
        if not os.path.exists(self.LATEX_BUILD_DIR):
            os.makedirs(self.LATEX_BUILD_DIR)
            logging.warning(f"Latex build directory created : {self.LATEX_BUILD_DIR}")

    def _get_template_args(self, **kwargs):
        return {}

    def render_latex(self, **kwargs):
        template = self.latex_jinja_env.get_template(self.template)
        baretable = template.render(**self._get_template_args(**kwargs))
        standalone_template = self.latex_jinja_env.get_template("STANDALONE.tex")
        return baretable, standalone_template.render(TABLE=baretable)

    def _get_barelatex_filename(self, filename):
        return filename + ".tex"

    def render_pdf(self, show_latex=False, verbose=False, filename=None, **kwargs):
        barelatex, latex = self.render_latex(**kwargs)
        if show_latex:
            print(latex)

        filename = self._get_barelatex_filename(filename)
        path = os.path.join(self.LATEX_EXPORT_PATH, filename)
        with open(path, "w", encoding="utf8") as f:
            f.write(barelatex)
        logging.info(f"Bare latex wrote in {path}")
        cwd = os.path.abspath(os.getcwd())
        os.chdir(self.LATEX_BUILD_DIR)
        with open(filename, "w", encoding="utf8") as f:
            f.write(latex)
        command = ["pdflatex", "-interaction", "batchmode", filename]
        rep = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if verbose:
            logging.debug(rep.stdout)
        if rep.stderr:
            logging.error(rep.stderr)
        else:
            logging.info(f"Standalone pdf wrote in {os.path.abspath(filename)}")
        os.chdir(cwd)


class abstractLatexTableWriter(abstractLatexWriter):
    """Builds latex template and runs pdflatex.
    This class transforms mesures into uniformed representation matrix, where one line represents one context.
    """

    LATEX_EXPORT_PATH = "../latex/tables"

    FACTOR_NUMBERS = 100
    """Multiply errors by this factor"""


    CRITERES = ["compareF", "meanPred", "modalPred", "retrouveYmean",
                "retrouveY", "retrouveYbest", "validPreds"]


    MEASURE_class = None
    """Measure class which gives experiences and methods"""

    TITLE = ""
    """Latex table title """

    DESCRIPTION = ""
    """Latex table caption"""


    METHODES = None
    """Default to Measure_class.METHODES"""


    def __init__(self):
        super(abstractLatexTableWriter, self).__init__()
        self.CATEGORIE = self.MEASURE_class.__name__
        mesures = Archive.load_mesures(self.CATEGORIE)
        self.experiences = self.MEASURE_class.experiences
        self.methodes = self.METHODES or self.MEASURE_class.METHODES
        self.matrix = self._mesures_to_matrix(mesures)
        self.matrix = self._find_best()


    def _find_best(self):
        """Find best value for each CRITERE, line per line"""
        m = []

        def best(line):
            l = [(i, c["mean"]) for i, c in enumerate(line) if c]
            l2 = [(i, c["median"]) for i, c in enumerate(line) if c]
            b = sorted(l, key=lambda d: d[1])[0][0] if len(l) > 0 else None
            b2 = sorted(l2, key=lambda d: d[1])[0][0] if len(l2) > 0 else None
            return b, b2

        for line in self.matrix:
            for key in set(self.CRITERES) - {"validPreds"}:
                values = [case[key] if (key in case) else None for case in line]
                bmean, bmedian = best(values)
                if bmean is not None:  # adding indicator of best
                    line[bmean][key]["mean"] = (line[bmean][key]["mean"], True)
                if bmedian is not None:
                    line[bmedian][key]["median"] = (line[bmedian][key]["median"], True)
            m.append(line)
        return m

    def _mesures_to_matrix(self, mesures):
        """Put measure in visual order. needs to synchronise with header data"""
        return [[mes[meth] for meth in self.methodes] for mes in mesures]

    def _horizontal_header(self):
        return self.methodes

    def _vertical_header(self):
        # adding  dimensions
        for exp in self.experiences:
            cc = exp["context"](exp["partiel"])
            exp["D"] = cc.D
            exp["L"] = cc.L
            exp["variables"] = cc.variables_names
        return self.experiences

    def _get_template_args(self, **kwargs):
        label = kwargs.pop("label", None) or self.CATEGORIE
        WITH_STD = kwargs.pop("WITH_STD", False)
        return dict(MATRIX=self.matrix, title=self.TITLE, description=self.DESCRIPTION,
                                    hHeader=self._horizontal_header(), vHeader=self._vertical_header(),
                                    label=label, CRITERES=self.CRITERES,
                                    FACTOR_NUMBERS=self.FACTOR_NUMBERS, WITH_STD=WITH_STD,
                                    NB_COL_CELL=3 if WITH_STD else 2)

    def _get_barelatex_filename(self, filename):
        return (filename or self.CATEGORIE) + '.tex'


class AlgosMeasure(abstractMeasures):
    METHODES = ["NG", "NjG", "NdG"]
    experiences = ALGOS_exps

    def _dic_mesures(self,i,exp,exp_params,t):
        dic = {}
        t = _load_train_measure_gllim(i, GLLiM, exp, dict(exp_params, get_rnk_init=True), NOISE, "sobol", t,
                                      t)  # noisy GLLiM
        if type(t) is dict:  # error
            dic["NG"] = t
        else:
            dic["NG"], exp_params["rnk_init"] = t  # fixed rnk
        Xtest, Ytest = exp.Xtest, exp.Ytest  # fixed test values

        dic["NjG"] = _load_train_measure_gllim(i, jGLLiM, exp, exp_params, NOISE, "sobol", False, t, Xtest=Xtest,
                                               Ytest=Ytest)  # noisy joint GLLiM
        dic["NdG"] = _load_train_measure_gllim(i, dGLLiM, exp, exp_params, NOISE, "sobol", False, t, Xtest=Xtest,
                                               Ytest=Ytest)  # noisy dGLLiM
        return dic

class GenerationMeasure(abstractMeasures):
    METHODES = ["random", "latin", "sobol"]
    experiences = GENERATION_exps

    def _dic_mesures(self,i,exp,exp_params,t):
        dic = {}
        dic['sobol'] = _load_train_measure_gllim(i, GLLiM, exp, exp_params, NOISE, "sobol", t, t)  # sobol
        Xtest, Ytest = exp.Xtest, exp.Ytest  # fixed test values
        dic['latin'] = _load_train_measure_gllim(i, GLLiM, exp, exp_params, NOISE, "latin", False, t, Xtest=Xtest,
                                                 Ytest=Ytest)  # latin
        dic['random'] = _load_train_measure_gllim(i, GLLiM, exp, exp_params, NOISE, "random", False, t, Xtest=Xtest,
                                                  Ytest=Ytest)  # random
        return dic

class DimensionMeasure(abstractMeasures):
    METHODES = ["gllim"]
    experiences = DIMENSION_exps

    def _dic_mesures(self, i, exp: Experience, exp_params, t):
        dic = {"gllim": _load_train_measure_gllim(i, jGLLiM, exp, exp_params, None, "sobol", t, t)}
        return dic


class ModalMeasure(abstractMeasures):
    METHODES = ["gllim"]
    experiences = MODAL_exps

    def _dic_mesures(self, i, exp, exp_params, t):
        if isinstance(exp.context, context.abstractExpFunction):
            exp.context.PREFERED_MODAL_PRED = 1
        dic = {"gllim": _load_train_measure_gllim(i, jGLLiM, exp, exp_params, None, "sobol", t, t)}
        return dic


class LogistiqueMeasure(abstractMeasures):
    METHODES = ["gllim"]
    experiences = LOGISTIQUE_exps

    def _dic_mesures(self, i, exp, exp_params, t):
        dic = {"gllim": _load_train_measure_gllim(i, GLLiM, exp, exp_params, NOISE, "sobol", t, t)}
        return dic


class NoisesMeasure(abstractMeasures):
    METHODES = ["no", "50", "10"]
    experiences = NOISES_exps

    def _dic_mesures(self, i, exp, exp_params, t):
        dic = {}
        Xtest, Ytest = exp._genere_data(exp.DEFAULT_NTEST, "sobol", 20)
        dic["50"] = _load_train_measure_gllim(i, jGLLiM, exp, exp_params, 50, "sobol", t, t, Xtest=Xtest, Ytest=Ytest)
        dic["no"] = _load_train_measure_gllim(i, jGLLiM, exp, exp_params, None, "sobol", t, t, Xtest=Xtest, Ytest=Ytest)
        dic["10"] = _load_train_measure_gllim(i, jGLLiM, exp, exp_params, 10, "sobol", t, t, Xtest=Xtest, Ytest=Ytest)
        return dic


class LocalMeasure(abstractMeasures):
    METHODES = ["no", "10", "100", "1000"]
    experiences = LOCAL_exps

    def _dic_mesures(self, i, exp, exp_params, t):
        dic = {}
        dic["no"] = _load_train_measure_gllim(i, dGLLiM, exp, dict(exp_params, init_local=None), NOISE, "sobol", t, t)
        Xtest, Ytest = exp.Xtest, exp.Ytest
        dic["10"] = _load_train_measure_gllim(i, dGLLiM, exp, dict(exp_params, init_local=10), NOISE, "sobol", False, t,
                                              Xtest=Xtest, Ytest=Ytest)
        dic["100"] = _load_train_measure_gllim(i, dGLLiM, exp, dict(exp_params, init_local=100), NOISE, "sobol", False,
                                               t,
                                               Xtest=Xtest, Ytest=Ytest)
        dic["1000"] = _load_train_measure_gllim(i, dGLLiM, exp, dict(exp_params, init_local=1000), NOISE, "sobol",
                                                False, t,
                                                Xtest=Xtest, Ytest=Ytest)
        return dic


class RelationCMeasure(abstractMeasures):
    METHODES = ["jgllim"]
    experiences = RELATIONC_exps

    def _dic_mesures(self, i, exp, exp_params, t):
        dic = {"jgllim": _load_train_measure_gllim(i, jGLLiM, exp, exp_params, NOISE, "sobol", t, t)}
        return dic


class PerComponentsMeasure(abstractMeasures):
    experiences = PARCOMPONENTS_exps
    METHODES = ["jgllim"]

    def _dic_mesures(self, i, exp, exp_params, t):
        dic = {"jgllim": _load_train_measure_gllim(i, jGLLiM, exp, exp_params, NOISE, "sobol", t, t)}
        return dic


class ClusteredPredictionMeasure(abstractMeasures):
    experiences = CLUSTERED_PREDICTION_exps
    METHODES = ["jGLLiM"]

    def _dic_mesures(self, i, exp: Experience, exp_params, t):
        r = _load_train_gllim(i, jGLLiM, exp, exp_params, NOISE, "sobol", t, t)
        if type(r) is dict:  # error
            return r
        gllim, training_time = r
        mo_c, y_c, ybest_c = exp.mesures._nrmse_clustered_prediction(gllim, nb_predsMax=2,
                                                                     size_sampling=100000, agg_method="max")
        mo_c_mean, y_c_mean, ybest_c_mean = exp.mesures._nrmse_clustered_prediction(gllim, nb_predsMax=2,
                                                                                    size_sampling=100000,
                                                                                    agg_method="mean")
        dic = dict(exp.mesures.run_mesures(gllim),
                   clusteredPred=exp.mesures.sumup_errors(mo_c),
                   retrouveYclustered=exp.mesures.sumup_errors(y_c),
                   retrouveYbestclustered=exp.mesures.sumup_errors(ybest_c),
                   clusteredPredMean=exp.mesures.sumup_errors(mo_c_mean),
                   retrouveYclusteredMean=exp.mesures.sumup_errors(y_c_mean),
                   retrouveYbestclusteredMean=exp.mesures.sumup_errors(ybest_c_mean),
                   training_time=training_time)
        return {"jGLLiM": dic}



### ----------------------------- LATEX WRTIERS ------------------------------- ###


class AlgosLatexWriter(abstractLatexTableWriter):
    MEASURE_class = AlgosMeasure
    template = "algos.tex"
    TITLE = "GLLiM et variantes"
    DESCRIPTION = f"Chaque algorithme est testé avec un dictionnaire légèrement bruité ($r = {NOISE}$)"


class AlgosTimeLatexWriter(abstractLatexTableWriter):
    MEASURE_class = AlgosMeasure
    template = "time.tex"
    TITLE = "Temps d'apprentissage"
    DESCRIPTION = "Temps indicatif d'entrainement des différentes variantes."

    @classmethod
    def render(cls, **kwargs):
        kwargs["filename"] = "AlgosTime"
        kwargs["label"] = "AlgosTime"
        super().render(**kwargs)


class GenerationLatexWriter(abstractLatexTableWriter):
    MEASURE_class = GenerationMeasure
    template = "generation.tex"
    TITLE = "Méthode de génération"
    DESCRIPTION = "Le dictionnaire d'apprentissage est généré avec différents " \
                  "générateurs pseudo ou quasi aléatoires."


class DimensionLatexWriter(abstractLatexTableWriter):
    MEASURE_class = DimensionMeasure
    template = "dimension.tex"
    TITLE = "Influence de la dimension"
    DESCRIPTION = "La même fonction générique est apprise et inversée pour différentes dimensions."

    def _mesures_to_matrix(self, mesures):
        return [[mes["gllim"] for mes in mesures]]

    def _horizontal_header(self):
        return super()._vertical_header()

    def _vertical_header(self):
        return [self.experiences[0]]


class ModalLatexWriter(abstractLatexTableWriter):
    MEASURE_class = ModalMeasure
    template = "modal.tex"
    TITLE = "Mode de prévision"
    DESCRIPTION = """Comparaison des résultats de la prévision par la moyenne (Me,Yme) par rapport à la prévision par le mode (Ce,Yce,Yb). 
                  (Les colonnes sont respectivement la moyenne et la médiane des erreurs.)"""

    def _find_best(self):
        """Do nothing, since there is only on method by exp."""
        return self.matrix


class LogistiqueLatexWriter(abstractLatexTableWriter):
    MEASURE_class = LogistiqueMeasure
    template = "logistique.tex"
    TITLE = "Transformation logistique"
    DESCRIPTION = "Méthode standard (gauche) contre version avec transformation logistique (droite)"

    def _mesures_to_matrix(self, mesures):
        return [[mes["gllim"] for mes in mesures]]

    def _horizontal_header(self):
        return super()._vertical_header()

    def _vertical_header(self):
        return [self.experiences[0]]


class NoisesLatexWriter(abstractLatexTableWriter):
    MEASURE_class = NoisesMeasure
    template = "noises.tex"
    TITLE = "Bruitage des données"
    DESCRIPTION = "Comparaison des différentes intensités de bruit sur le dictionnaire d'apprentissage. " \
                  f"Les observations sont bruitées avec $r_{0} = 20$."


class LocalLatexWriter(abstractLatexTableWriter):
    MEASURE_class = LocalMeasure
    template = "local.tex"
    TITLE = "Initialisation locale"
    DESCRIPTION = "Comparaison pour différentes valeurs de la précision initiale."


class RelationCLatexWriter(abstractLatexTableWriter):
    MEASURE_class = RelationCMeasure
    template = "relationC.tex"
    TITLE = "Relation imposée entre $b$ et $c$"
    DESCRIPTION = "Comparaison entre un apprentissage standard et un apprentissage en déduisant $c$ de $b$."


class DoubleLearningWriter(abstractLatexTableWriter):
    template = "doublelearning.tex"
    TITLE = "Apprentissage adaptatif"
    DESCRIPTION = "Moyenne (et médianne) pour les mêmes {Ntest} données : apprentissage standard (gauche) " \
                  "contre apprentissage adaptatif (droite)"
    METHODES = ["first", "second"]

    def __init__(self):
        self.CATEGORIE = "SecondLearning"
        mesures = Archive.load_mesures(self.CATEGORIE)
        self.experiences = [{"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 200, "N": 10000,
                             "init_local": 200, "sigma_type": "full", "gamma_type": "full"},
                            {"context": context.InjectiveFunction(4), "partiel": None, "K": 100, "N": 10000,
                             "init_local": 200, "sigma_type": "iso", "gamma_type": "full"}
                            ]
        self.methodes = self.METHODES
        self.matrix = self._mesures_to_matrix(mesures)
        self.matrix = self._find_best()
        self.DESCRIPTION = self.DESCRIPTION.format(Ntest=mesures[0]["Ntest"])

    def _mesures_to_matrix(self, mesures):
        return [[exp[m] for m in self.methodes] for exp in mesures]


class ErrorPerComponentsWriter(abstractLatexTableWriter):
    MEASURE_class = PerComponentsMeasure
    template = "table_per_components.tex"
    TITLE = "Erreur variable par variable"
    DESCRIPTION = """Erreur (en valeur absolue) pour la prédiction par la moyenne. 
                  (Les colonnes sont respectivement la moyenne et la médiane des erreurs.)"""


class ClusteredPredictionWriter(abstractLatexTableWriter):
    MEASURE_class = ClusteredPredictionMeasure
    template = "clustered_pred.tex"
    TITLE = "Prédiction par moyenne locale"
    DESCRIPTION = "Etude la prédiction par la moyenne restreinte localement."
    CRITERES = ["meanPred", "modalPred", "retrouveYmean",
                "retrouveY", "retrouveYbest"] + ["clusteredPred", "retrouveYclustered",
                                                 "retrouveYbestclustered"]


class DescriptionContextWriter(abstractLatexWriter):
    template = "description_contexts.tex"

    LATEX_EXPORT_PATH = "../latex/rapport/NUMERIQUE"

    @classmethod
    def render(cls, **kwargs):
        kwargs["filename"] = "contexts"
        super().render(**kwargs)

    def _get_template_args(self, **kwargs):
        return {"CONTEXTS": kwargs["CONTEXTS"]}




def main():
    """Run test"""
    # AlgosMeasure.run([False, False, False, False, True], [False, False, False, False, True])
    # GenerationMeasure.run(True, True)
    # DimensionMeasure.run(True, True)
    # ModalMeasure.run(True, True)
    # LogistiqueMeasure.run(True, True)
    # NoisesMeasure.run(True, True)
    # LocalMeasure.run(True, True)
    # RelationCMeasure.run(True, True)
    # PerComponentsMeasure.run(True, True)
    # ClusteredPredictionMeasure.run([True, True], [True, True])

    # AlgosLatexWriter.render()
    # AlgosTimeLatexWriter.render()
    # GenerationLatexWriter.render()
    # DimensionLatexWriter.render()
    # ModalLatexWriter.render()
    # LogistiqueLatexWriter.render()
    # NoisesLatexWriter.render()
    # LocalLatexWriter.render()
    # RelationCLatexWriter.render()
    DoubleLearningWriter.render()
    # ErrorPerComponentsWriter.render()
    # ClusteredPredictionWriter.render()


if __name__ == '__main__':
    coloredlogs.install(level=logging.DEBUG, fmt="%(asctime)s : %(levelname)s : %(message)s",
                        datefmt="%H:%M:%S")
    main()
