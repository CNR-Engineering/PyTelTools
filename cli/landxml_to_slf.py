#!/usr/bin/env python
"""
Converts LandXML surfaces to 2D Selafin file
In case of multiple surfaces, they should have the same mesh (coordinates and connectivity table)
A single variable is written and its name is taken from the first surface name attribute
"""
import numpy as np
import sys
import xml.etree.ElementTree as ET

from pyteltools.slf import Serafin
from pyteltools.utils.cli_base import PyTelToolsArgParse


def landxml_to_slf(args):
    root = ET.parse(args.in_xml).getroot()
    PREFIX = '{http://www.landxml.org/schema/LandXML-1.2}'

    nodes = []  # list of (x, y) coordinates
    ikle = []  # list of triangle triplet (1-indexed)
    output_header = None
    with Serafin.Write(args.out_slf, args.lang, overwrite=args.force) as resout:
        for i, surface in enumerate(root.find(PREFIX + 'Surfaces')):
            surface_name = surface.get('name')
            if ' ' in surface_name:
                varname = surface_name.split(' ')[0]
            else:
                varname = surface_name
            # time_duration = surface_name.split(' ')[-1]
            tin = surface.find(PREFIX + 'Definition')
            values = []
            for j, pnts in enumerate(tin.find(PREFIX + 'Pnts')):
                assert int(pnts.get('id')) == j + 1
                y, x, z = (float(n) for n in pnts.text.split())
                values.append(z)
                if i == 0:
                    nodes.append((x, y))
                else:
                    if (x, y) != nodes[j]:
                        raise RuntimeError("Coordinates are not strictly identical")

            for j, face in enumerate(tin.find(PREFIX + 'Faces')):
                assert int(face.get('id')) == j + 1
                n1, n2, n3 = (int(n) for n in face.text.split())
                if i == 0:
                    ikle.append((n1, n2, n3))
                else:
                    if (n1, n2, n3) != ikle[j]:
                        raise RuntimeError("Mesh is not strictly identical")

            if i == 0:
                output_header = Serafin.SerafinHeader(title='Converted from LandXML (written by PyTelTools)')
                output_header.from_triangulation(np.array(nodes, dtype=np.int),
                                                 np.array(ikle, dtype=np.int))
                output_header.add_variable_str(varname, varname, '')
                resout.write_header(output_header)

            time = i * 3600.0  # FIXME: should convert time_duration to float
            resout.write_entire_frame(output_header, time, np.expand_dims(np.array(values), axis=0))


parser = PyTelToolsArgParse(description=__doc__)
parser.add_argument('in_xml', help='input LandXML file (with .xml extension)')
parser.add_known_argument('out_slf')
parser.add_group_general(['force', 'verbose'])


if __name__ == '__main__':
    args = parser.parse_args()

    try:
        landxml_to_slf(args)
    except (Serafin.SerafinRequestError, Serafin.SerafinValidationError):
        # Message is already reported by slf logger
        sys.exit(1)
