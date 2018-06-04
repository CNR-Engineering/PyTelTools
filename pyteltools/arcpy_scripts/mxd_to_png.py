import sys


try:
    import arcpy.mapping
except ModuleNotFoundError:
    sys.exit(1)

mxd_path, png_name = sys.argv[1], sys.argv[2]

try:
    mxd = arcpy.mapping.MapDocument(mxd_path)
    layers = arcpy.mapping.ListLayers(mxd)
except Exception as e:
    sys.stderr.write(str(e))
    sys.exit(2)

try:
    arcpy.mapping.ExportToPNG(mxd, png_name, resolution=96)
except Exception as e:
    sys.stderr.write(str(e))
    sys.exit(3)

sys.exit(0)
