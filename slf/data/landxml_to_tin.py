import sys

try:
    import arcpy
except ModuleNotFoundError:
    sys.exit(1)

xml_name, tin_name = sys.argv[1], sys.argv[2]

try:
    arcpy.CheckOutExtension('3D')  # obtain a license for the ArcGIS 3D Analyst extension
except:
    sys.exit(2)

try:
    arcpy.LandXMLToTin_3d(xml_name, '.', tin_name, '1')
except:
    sys.exit(3)

sys.exit(0)


