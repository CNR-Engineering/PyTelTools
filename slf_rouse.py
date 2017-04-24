# -*- coding: utf-8 -*-
#!/usr/bin/python3
"""
@brief:
Ajouter des varibles supplémentaires pour l'interprétation hydro-sédimentaire à partir d'un résultat 2D

@features:
* Tous les enregistrements temporels sont traités et toutes les variables initiales sont ré-écrites
* Il y a autant que de sédiments que nouvelles variables (une vitesse de chute par sédiment)
* Le Rouse est calculé à partir de la vitesse de chute ws et de la variable US (KARMAN = 0.4) avec la formule: Rouse = ws/(KARMAN*US)
* Le Rouse est affecté à -9999. dans les zones où l'on a l'un des deux cas suivants :
    - la vitesse de frottement est nulle (afin d'éviter la division par zéro)
    - la hauteur d'eau est inférieure à un seuil qui vaut par défaut 1cm et qui est personnalisable avec l'option `--h_corr`
* Le nom des variables ajoutées pour le nombre de Rouse peut être modifié par l'utilisateur avec l'option `--labels` (si l'option est manquante, le nom des variables est construit avec le preffixe 'SEDIMENT')
* Les variables suivantes sont ajoutés :
    - CONTRAINTE (en Pa) = RHO_EAU * US^2
    - DMAX (en mm) selon trois zones basées sur TAU (bornes : 0.1 et 0.34)

@warnings:
Les variables US et H doivent exister
"""


import os
import logging
import logging.config
import numpy as np
from common.arg_command_line import myargparse
import slf


# define script arguments
parser = myargparse(description=__doc__, add_args=['force', 'verbose'])
parser.add_argument('inname', help='Serafin input filename')
parser.add_argument('outname', help='Serafin output filename')
parser.add_argument('ws', help='Vitesses de chute (m/s)', type=float, nargs='+')
parser.add_argument('--lang', type=str, help='Language used in the input file (fr or en)', default='fr')
parser.add_argument('--labels', help='Nom des variables (sans accents ou caractères spéciaux)', nargs='+')
parser.add_argument('--h_corr', help='hauteur seuil pour correction (par défaut : 1cm)', type=float, default=0.01)
args = parser.parse_args()

# handle the verbosity/debug option
levels = ['WARNING', 'INFO', 'DEBUG']
loglevel = levels[min(len(levels)-1, args.verbose)]  # capped to number of levels

# apply logging configurations
logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: \n%(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': loglevel,
            'class': 'logging.StreamHandler',
            'formatter': 'standard'
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'formatter': 'standard',
            'filename': os.path.join(os.path.dirname(__file__), 'log', '%s.log' % __file__[:-3])
        }
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True
        }
    }
})

# create a logger
logger = logging.getLogger(__name__)

# running the script
logger.info('Start running the script..')

# ==================================================================
# =========== here goes the script =================================

# define constants
KARMAN = 0.4
DEFAULT_VAR_PREFIX = 'SEDIMENT'
DEFAULT_VALUE = -9999.
RHO_EAU = 1000.  # kg/m3


# define helper functions
def can_compute_rouse(slf_file):
    """
    @brief: determine if Rouse variables can be computed from the given .slf file
    @param slf_file <Serafin.Read>: a Serafin.Read object
    @return <bool>: True is Rouse variables can be computed
    """
    return 'US' in slf_file.var_IDs and 'H' in slf_file.varIDs


def handle_additional_calculations():
    pass  # TODO


# validate arguments
nb_sediments = len(args.ws)

if args.labels is not None:
    if nb_sediments != len(args.labels):
        logger.error('ERROR: The number of labels is not equal to the number of sediments')
        raise RuntimeError("Il n'y a pas %d noms de variables" % nb_sediments)
    new_var_names = args.labels
    if any(map(lambda name: len(name) > 16, new_var_names)):
        raise RuntimeError("Le nom de la variable est trop long (limite de 16 caractères)")
else:
    new_var_names = list(map(lambda i: DEFAULT_VAR_PREFIX + ' ' + str(i+1), range(len(args.ws))))


# calculations
with slf.Serafin.Read(args.inname) as resin:
    resin.read_header()
    resin.get_time()

    if not can_compute_rouse(resin):
        handle_additional_calculations()

    pos_H = resin.header.var_ID_to_index('H')
    pos_US = resin.header.var_ID_to_index('US')

    with slf.Serafin.Write(args.outname, args.force) as resout:
        resout.copy_header(resin.header)

        # add variables before write header
        resout.header.nb_var = resin.nb_var + nb_sediments + 2
        resout.header.var_names.extend(map(lambda x: bytes(x.ljust(16)), new_var_names))
        resout.header.var_units.extend([] * nb_sediments + [b'PASCAL          ', b'MM              '])

        resout.write_header()

# ==================================================================
logger.info('Finished!')







