"""
Update node numbering in a file describing culverts
"""

import sys

from pyteltools.conf import settings
from pyteltools.slf import Serafin
from pyteltools.utils.cli_base import PyTelToolsArgParse


def update_culverts_file(args):
    with Serafin.Read(args.in_slf_ori, args.lang) as mesh_ori:
        mesh_ori.read_header()
    with Serafin.Read(args.in_slf_new, args.lang) as mesh_new:
        mesh_new.read_header()
    with open(args.in_txt, 'r') as in_txt:
        with open(args.out_txt, 'w', newline='') as out_txt:
            for i, line in enumerate(in_txt):
                if i < 3:
                    out_txt.write(line)
                else:
                    n1_ori, n2_ori, txt = line.split(maxsplit=2)
                    n1_new = mesh_new.header.nearest_node(mesh_ori.header.x[int(n1_ori) - 1],
                                                          mesh_ori.header.y[int(n1_ori) - 1])
                    n2_new = mesh_new.header.nearest_node(mesh_ori.header.x[int(n2_ori) - 1],
                                                          mesh_ori.header.y[int(n2_ori) - 1])
                    out_txt.write('%i %i %s' % (n1_new, n2_new, txt))


parser = PyTelToolsArgParse(description=__doc__, add_args=[])
parser.add_argument('in_txt', help='Original input culverts file')
parser.add_argument('out_txt', help='New output culverts file')
parser.add_argument('in_slf_ori', help='Original Serafin file')
parser.add_argument('in_slf_new', help='New Serafin file')
parser.add_argument('--lang', help="Serafin language for variables detection: 'fr' or 'en'", default=settings.LANG)
parser.add_group_general(['force', 'verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        update_culverts_file(args)
    except (Serafin.SerafinRequestError, Serafin.SerafinValidationError):
        # Message is already reported by slf logger
        sys.exit(1)
