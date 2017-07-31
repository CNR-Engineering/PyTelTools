import sys

try:
    import arcpy.mapping
except ModuleNotFoundError:
    sys.exit(1)

mxd_path, png_name = sys.argv[1], sys.argv[2]

try:
    mxd = arcpy.mapping.MapDocument(mxd_path)
    layers = arcpy.mapping.ListLayers(mxd)
except:
    sys.exit(2)

try:
    arcpy.mapping.ExportToPNG(mxd, png_name, resolution=96)
except:
    sys.exit(3)
