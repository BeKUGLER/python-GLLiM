"""Sums up several tests on different contexts. Runs tests and saves results in json File.
Then translates this file into latex table.
"""
import os
import subprocess
import time
import warnings
from datetime import timedelta
import logging

import coloredlogs
import jinja2
import numpy as np

from Core.dgllim import dGLLiM
from Core.gllim import GLLiM, jGLLiM, WrongContextError
from experiences import logistic
from hapke import relation_C
from tools import context
from tools.archive import Archive
from tools.experience import SecondLearning

warnings.filterwarnings("ignore")

NOISE = 50

ALGOS_exps = [
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 1000, "N": 10000,
     "init_local": 200, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": None, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.HapkeGonio1468_50, "partiel": (0, 1, 2, 3), "K": 1000, "N": 10000,
     "init_local": None, "sigma_type": "iso", "gamma_type": "full"},
    {"context": context.HapkeGonio1468_50, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": None, "sigma_type": "iso", "gamma_type": "full"},
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
    {"context": context.InjectiveFunction(1), "partiel": None, "K": 100, "N": 1000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"}
]

LOGISTIQUE_exps = [
    {"context": context.LabContextOlivine, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": 200, "sigma_type": "full", "gamma_type": "full"},
    {"context": logistic.LogisticOlivineContext, "partiel": (0, 1, 2, 3), "K": 100, "N": 100000,
     "init_local": 200, "sigma_type": "full", "gamma_type": "full"}
]

NOISES_exps = [
    {"context": context.InjectiveFunction(1), "partiel": None, "K": 100, "N": 5000,
     "init_local": 100, "sigma_type": "full", "gamma_type": "full"},
    {"context": context.WaveFunction, "partiel": None, "K": 100, "N": 5000,
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
    {"context": context.HapkeContext, "partiel": (0, 1, 2, 3), "K": 1000, "N": 10000,
     "init_local": None, "sigma_type": "full", "gamma_type": "full"},
    {"context": relation_C.HapkeCRelationContext, "partiel": (0, 1, 2), "K": 1000, "N": 10000,
     "init_local": None, "sigma_type": "full", "gamma_type": "full"}
]


def _load_train_gllim(i, gllim_cls, exp, exp_params, noise, method, redata, retrain, Xtest=None, Ytest=None):
    """If Xtest and Ytest are given, use instead of exp data.
    Useful to fix data across severals exp"""
    logging.info("  Starting {name} (K = {K}, N = {N})  ...".format(name=gllim_cls.__name__, **exp_params))
    ti = time.time()
    try:
        exp.load_data(regenere_data=redata, with_noise=noise, N=exp_params["N"], method=method)
        gllim1, training_time = exp.load_model(exp_params["K"], mode=retrain and "r" or "l",
                                               init_local=exp_params["init_local"],
                                               sigma_type=exp_params["sigma_type"], gamma_type=exp_params["gamma_type"],
                                               gllim_cls=gllim_cls, with_time=True)
    except FileNotFoundError as e:
        logging.warning(
            "--- No model or data found for experience {}, version {} - noise : {} ---".format(i + 1,
                                                                                               gllim_cls.__name__,
                                                                                               noise))
        logging.debug(e)
        return None
    except WrongContextError as e:
        logging.warning("\t{} method is not appropriate for the parameters ! "
              "Details \n\t{} \n\tIgnored".format(gllim_cls.__name__, e))
        return None
    except np.linalg.LinAlgError as e:
        logging.error("\tTraining failed ! {}".format(e))
        return None
    except AssertionError as e:
        logging.error("\tTraining failed ! {}".format(e))
        return None
    logging.info("  Model fitted or loaded in {:.3f} s".format(timedelta(seconds=time.time() - ti)))
    ti = time.time()
    if Xtest is not None:
        exp.Xtest, exp.Ytest = Xtest, Ytest
    else:
        exp.centre_data_test()
    m = exp.mesures.run_mesures(gllim1)
    m["training_time"] = training_time
    logging.info("Mesures done in {} s".format(timedelta(seconds=time.time() - ti)))
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
                logging.info(f"Tests {self.CATEGORIE} exp. {i+1}/{imax}")
                exp = SecondLearning(exp_params["context"], partiel=exp_params["partiel"], verbose=None)
                dGLLiM.dF_hook = exp.context.dF
                dic = self._dic_mesures(i,exp,exp_params,t)
                if dic is not None:
                    assert set(self.METHODES) <= set(dic.keys()), f"Missing measures for {self.CATEGORIE}"
            else:
                logging.info("Loaded mesures {}/{}".format(i + 1, imax))
                dic = old_mesures[i]
            mesures.append(dic)
        Archive.save_mesures(mesures, self.CATEGORIE)
        logging.info("Study carried in {} \n".format(timedelta(seconds=time.time() - ti)))


    def _dic_mesures(self,i,exp,exp_params,t):
        return {}


class abstractLatexWriter():
    """Builds latex template and runs pdflatex.
    This class transforms mesures into uniformed representation matrix, where one line represents one context.
    """

    LATEX_BUILD_DIR = "latex_build"

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
        autoescape=False,
        loader=jinja2.FileSystemLoader("templates_latex"),

    )
    latex_jinja_env.globals.update(zip=zip)
    latex_jinja_env.filters["timespent"] = lambda s: time.strftime("%M m %S s", time.gmtime(s))

    CRITERES = ["compareF", "meanPred", "modalPred", "retrouveYmean", "retrouveY", "retrouveYbest"]

    LATEX_EXPORT_PATH = "../latex/tables"
    """Saving directory for bare latex table"""

    MEASURE_class = None
    """Measure class which gives experiences and methods"""

    TITLE = ""
    """Latex table title """

    DESCRIPTION = ""
    """Latex table caption"""

    template = ""
    "latex template file"

    METHODES = None
    """Default to Measure_class.METHODES"""

    @classmethod
    def render(cls, **kwargs):
        """Wrapper"""
        w = cls()
        w.render_pdf(**kwargs)

    def __init__(self):
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
            for key in self.CRITERES:
                values = [case[key] if case else None for case in line]
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
        return self.experiences

    def render_latex(self):
        template = self.latex_jinja_env.get_template(self.template)
        CRITERES = self.CRITERES + ["validPreds"]
        baretable = template.render(MATRIX=self.matrix, title=self.TITLE, description=self.DESCRIPTION,
                                    hHeader=self._horizontal_header(), vHeader=self._vertical_header(),
                                    label=self.CATEGORIE, CRITERES=CRITERES)
        standalone_template = self.latex_jinja_env.get_template("STANDALONE.tex")
        return baretable, standalone_template.render(TABLE=baretable)

    def render_pdf(self, show_latex=False, verbose=False, filename=None):
        barelatex, latex = self.render_latex()
        if show_latex:
            print(latex)

        filename = (filename or self.CATEGORIE) + '.tex'
        path = os.path.join(self.LATEX_EXPORT_PATH, filename)
        with open(path, "w", encoding="utf8") as f:
            f.write(barelatex)
        cwd = os.path.abspath(os.getcwd())
        os.chdir(self.LATEX_BUILD_DIR)
        with open(filename, "w", encoding="utf8") as f:
            f.write(latex)
        command = ["pdflatex", "-interaction", "batchmode", filename]
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        rep = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # for longtable package
        if verbose:
            logging.debug(rep.stdout)
        if rep.stderr:
            logging.error(rep.stderr)
        else:
            logging.info("Latex compilation done.")
        os.chdir(cwd)



class AlgosMeasure(abstractMeasures):
    METHODES = ["NG", "NjG", "NdG"]
    experiences = ALGOS_exps

    def _dic_mesures(self,i,exp,exp_params,t):
        dic = {}
        # dic['nNG'] = _load_train_gllim(i, GLLiM, exp, exp_params, None, "sobol", t, t)  # no noise GLLiM
        # Xtest, Ytest = exp.Xtest, exp.Ytest  # fixed test values
        # dic["nNdG"] = _load_train_gllim(i, dGLLiM, exp, exp_params, None, "sobol", False, t,Xtest=Xtest,Ytest=Ytest)  # no noise dGLLiM
        # dic["nNjG"] = _load_train_gllim(i, jGLLiM, exp, exp_params, None, "sobol", False, t, Xtest=Xtest,
        #                                 Ytest=Ytest)  # no noise joint GLLiM
        dic["NG"] = _load_train_gllim(i, GLLiM, exp, exp_params, NOISE, "sobol", t, t)  # noisy GLLiM
        Xtest, Ytest = exp.Xtest, exp.Ytest  # fixed test values
        dic["NdG"] = _load_train_gllim(i, dGLLiM, exp, exp_params, NOISE, "sobol", False, t,Xtest=Xtest,Ytest=Ytest)  # noisy dGLLiM
        dic["NjG"] = _load_train_gllim(i, jGLLiM, exp, exp_params, NOISE, "sobol", False, t, Xtest=Xtest,
                                       Ytest=Ytest)  # noisy joint GLLiM
        return dic

class GenerationMeasure(abstractMeasures):
    METHODES = ["random", "latin", "sobol"]
    experiences = GENERATION_exps

    def _dic_mesures(self,i,exp,exp_params,t):
        dic = {}
        dic['sobol'] = _load_train_gllim(i, GLLiM, exp, exp_params, NOISE, "sobol", t, t)  # sobol
        Xtest, Ytest = exp.Xtest, exp.Ytest  # fixed test values
        dic['latin'] = _load_train_gllim(i, GLLiM, exp, exp_params, NOISE, "latin", t, t,Xtest=Xtest,Ytest=Ytest)  # latin
        dic['random'] = _load_train_gllim(i, GLLiM, exp, exp_params, NOISE, "random", t, t,Xtest=Xtest,Ytest=Ytest)  # random
        return dic

class DimensionMeasure(abstractMeasures):
    METHODES = ["gllim"]
    experiences = DIMENSION_exps

    def _dic_mesures(self, i, exp: SecondLearning, exp_params, t):
        dic = {"gllim": _load_train_gllim(i,GLLiM,exp,exp_params,None,"sobol",t,t)}
        return dic


class ModalMeasure(abstractMeasures):
    METHODES = ["gllim"]
    experiences = MODAL_exps

    def _dic_mesures(self, i, exp, exp_params, t):
        dic = {"gllim": _load_train_gllim(i, GLLiM, exp, exp_params, None, "sobol", t, t)}
        return dic


class LogistiqueMeasure(abstractMeasures):
    METHODES = ["gllim"]
    experiences = LOGISTIQUE_exps

    def _dic_mesures(self, i, exp, exp_params, t):
        dic = {"gllim": _load_train_gllim(i, GLLiM, exp, exp_params, NOISE, "sobol", t, t)}
        return dic


class NoisesMeasure(abstractMeasures):
    METHODES = ["no", "50", "10"]
    experiences = NOISES_exps

    def _dic_mesures(self, i, exp, exp_params, t):
        dic = {}
        dic["no"] = _load_train_gllim(i, GLLiM, exp, exp_params, None, "sobol", t, t)
        dic["10"] = _load_train_gllim(i, GLLiM, exp, exp_params, 10, "sobol", t, t)
        dic["50"] = _load_train_gllim(i, GLLiM, exp, exp_params, 50, "sobol", t, t)
        return dic


class LocalMeasure(abstractMeasures):
    METHODES = ["no", "10", "100", "1000"]
    experiences = LOCAL_exps

    def _dic_mesures(self, i, exp, exp_params, t):
        dic = {}
        dic["no"] = _load_train_gllim(i, dGLLiM, exp, dict(exp_params, init_local=None), NOISE, "sobol", t, t)
        Xtest, Ytest = exp.Xtest, exp.Ytest
        dic["10"] = _load_train_gllim(i, dGLLiM, exp, dict(exp_params, init_local=10), NOISE, "sobol", False, t,
                                      Xtest=Xtest, Ytest=Ytest)
        dic["100"] = _load_train_gllim(i, dGLLiM, exp, dict(exp_params, init_local=100), NOISE, "sobol", False, t,
                                       Xtest=Xtest, Ytest=Ytest)
        dic["1000"] = _load_train_gllim(i, dGLLiM, exp, dict(exp_params, init_local=1000), NOISE, "sobol", False, t,
                                        Xtest=Xtest, Ytest=Ytest)
        return dic


class RelationCMeasure(abstractMeasures):
    METHODES = ["dgllim"]
    experiences = RELATIONC_exps

    def _dic_mesures(self, i, exp, exp_params, t):
        dic = {"dgllim": _load_train_gllim(i, dGLLiM, exp, exp_params, NOISE, "latin", t, t)}
        return dic


### ----------------------------- LATEX WRTIERS ------------------------------- ###


class AlgosLatexWriter(abstractLatexWriter):
    MEASURE_class = AlgosMeasure
    template = "algos.tex"
    TITLE = "Algorithmes"
    DESCRIPTION = "Chaque algorithme est testé avec un dictionnaire légèrement bruité."


class AlgosTimeLatexWriter(abstractLatexWriter):
    MEASURE_class = AlgosMeasure
    template = "time.tex"
    TITLE = "Temps d'apprentissage"
    DESCRIPTION = "Temps indicatif d'entrainement des différentes variantes."

    @classmethod
    def render(cls, **kwargs):
        kwargs["filename"] = "AlgosTime"
        super().render(**kwargs)


class GenerationLatexWriter(abstractLatexWriter):
    MEASURE_class = GenerationMeasure
    template = "generation.tex"
    TITLE = "Méthode de génération"
    DESCRIPTION = "Le dictionnaire d'aprentissage est généré avec différentes méthodes de génération " \
                  "de nombres aléatoires."


class DimensionLatexWriter(abstractLatexWriter):
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


class ModalLatexWriter(abstractLatexWriter):
    MEASURE_class = ModalMeasure
    template = "modal.tex"
    TITLE = "Mode de prévision"
    DESCRIPTION = "Comparaison des résultats de la prévision par la moyenne (Me,Yme) " \
                  "par rapport à la prévision par le mode (Mo,Ymo,Yb)"


class LogistiqueLatexWriter(abstractLatexWriter):
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


class NoisesLatexWriter(abstractLatexWriter):
    MEASURE_class = NoisesMeasure
    template = "noises.tex"
    TITLE = "Bruitage des données"
    DESCRIPTION = "Comparaison des différentes intensités de bruit sur les observations."


class LocalLatexWriter(abstractLatexWriter):
    MEASURE_class = LocalMeasure
    template = "local.tex"
    TITLE = "Initialisation locale"
    DESCRIPTION = "Comparaison pour différentes valeurs de la précision initiale."

# run_self.mesures(train=[False] *  13 + [True] * 2 ,
#             run_mesure=[False] * 13 + [True] * 2 )
# mesuresAlgos(train=False,run_mesure=False)
# GenerationMeasure.run(train=False,run_mesure=True)


class RelationCLatexWriter(abstractLatexWriter):
    MEASURE_class = RelationCMeasure
    template = "relationC.tex"
    TITLE = "Relation imposée entre $b$ et $c$"
    DESCRIPTION = "Comparaison entre un apprentissage standard et un apprentissage en déduisant $c$ de $b$."



def main():
    # AlgosMeasure.run(True, True)
    # GenerationMeasure.run(True, True)
    # DimensionMeasure.run(True, True)
    # ModalMeasure.run(True, True)
    # LogistiqueMeasure.run(True, True)
    # NoisesMeasure.run(True, True)
    # LocalMeasure.run([False,False,True], True)
    # RelationCMeasure.run(True, True)
    #
    # AlgosLatexWriter.render()
    # AlgosTimeLatexWriter.render()
    # GenerationLatexWriter.render()
    # DimensionLatexWriter.render()
    # ModalLatexWriter.render()
    # LogistiqueLatexWriter.render()
    # NoisesLatexWriter.render()
    # LocalLatexWriter.render()
    RelationCLatexWriter.render()

if __name__ == '__main__':
    coloredlogs.install(level=logging.INFO, fmt="%(asctime)s : %(levelname)s : %(message)s",
                        datefmt="%H:%M:%S")
    main()
