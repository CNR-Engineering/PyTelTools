from geom import BlueKenue


with BlueKenue.Read('/home/lucd/data/polygones_volumes.i2s') as f:
    # Read header
    f.read_header()

    # Read polylines
    for i, polyline in enumerate(f.get_polygons()):
        print(polyline)
