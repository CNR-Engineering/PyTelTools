from slf.volume import *
from geom import BlueKenue
from slf import Serafin
import time



def volume():
    with BlueKenue.Read('testdata/mypoly.i2s') as f:
    # with BlueKenue.Read('T:\\Utilisateurs\\Wang\\Cas_test_Loire\\polygones_test_helio.i2s') as f:
    # with BlueKenue.Read('T:\\Utilisateurs\\Wang\\Cas_test_Loire\\grosPolygone.i2s') as f:

        f.read_header()
        polygons = []
        names = []
        for poly_name, poly in f:
            names.append(str(poly_name[1]))
            polygons.append(poly)

    with Serafin.Read('testdata\\test.slf', 'fr') as f:
    # with Serafin.Read('T:\\Utilisateurs\\Wang\\Cas_test_Loire\\sis_res_onlyB.slf', 'fr') as f:
        f.read_header()
        f.get_time()

        # with open('testdata/testVolumeU3.csv', 'w') as f2:
        #     volume_net_strict('U', f, f2, names, polygons)

        with open('testdata/testVolumeUextra4.csv', 'w') as f2:
            volume_net('U', f, f2, names, polygons)

        # with open('testdata/testVolumeUsup3.csv', 'w') as f2:
        #     volume_superior('U', f, f2, names, polygons)



#
t0 = time.time()
volume()
print(time.time() - t0)


