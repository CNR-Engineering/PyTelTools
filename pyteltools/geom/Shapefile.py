# pylint: disable=C0326
"""!
Read and write .shp files
"""

import numpy as np
import os
import shapefile
from shapefile import ShapefileException as ShpException
from struct import pack, error

from .geometry import Polyline


def get_shape_type(input_filename):
    sf = shapefile.Reader(input_filename)
    return sf.shapeType


def get_lines(input_filename, shape_type):
    sf = shapefile.Reader(input_filename)
    for record in sf.shapeRecords():
        if record.shape.shapeType == shape_type:
            attributes = record.record
            if shape_type > 10:
                poly = Polyline(record.shape.points, attributes, record.shape.z)
            else:
                poly = Polyline(record.shape.points, attributes)
            yield poly


def get_open_polylines(input_filename):
    try:
        shape_type = get_shape_type(input_filename)
        if shape_type in (3, 13):
            for poly in get_lines(input_filename, shape_type):
                yield poly
    except error:
        raise ShpException('Error while reading Shapefile. Inconsistent bytes.')


def get_polygons(input_filename):
    try:
        shape_type = get_shape_type(input_filename)
        if shape_type in (5, 15):
            for poly in get_lines(input_filename, shape_type):
                yield poly
    except error:
        raise ShpException('Error while reading Shapefile. Inconsistent bytes.')


def get_all_fields(input_filename):
    """!
    Get all fields characteristics of a shapefile
    @param input_filename <str>: path to shapefile
    @return <list([str, str, int, int])>: list composed of a tuple (attribute name, attribute type, length and
        precision) for each field
    """
    sf = shapefile.Reader(input_filename)
    return sf.fields[1:]


def get_attribute_names(input_filename):
    """!
    Get attributes (except the M value) of a shapefile
    @param input_filename <str>: path to shapefile
    @return <[str], [int]>: list of field names and indices
    """
    names, indices = [], []
    for i, (field_name, field_type, _, _) in enumerate(get_all_fields(input_filename)):
        if field_type == 'M':
            continue
        else:
            indices.append(i)
            if type(field_name) == bytes:
                names.append(field_name.decode('latin-1'))
            else:
                names.append(field_name)
    return names, indices


def get_numeric_attribute_names(input_filename):
    """!
    Get all numeric attributes of a shapefile
    @param input_filename <str>: path to shapefile
    @return <[(int, str)>: list of field names and indices
    """
    for i, (field_name, field_type, _, _) in enumerate(get_all_fields(input_filename)):
        if field_type == 'N' or field_type == 'F':
            if type(field_name) == bytes:
                field_name = field_name.decode('latin-1')
            yield i, field_name


def get_points(input_filename, indices=None, with_z=False):
    """!
    Get specific points (coordinates and attributes) from a shapefile
    @param input_filename <str>: path to shapefile
    @param indices <[int]>: indices of points
    @param with_z <bool>: extract z coordinate
    @return <tuple([(x, y, (z)), list(float)])>: tuple of coordinates and list of corresponding field values
    """
    try:
        sf = shapefile.Reader(input_filename)
        for record in sf.shapeRecords():
            if record.shape.shapeType in [1, 11, 21]:
                attributes = record.record
                decoded_attributes = []
                for attribute in attributes:
                    if type(attribute) == bytes:
                        decoded_attributes.append(attribute.decode('latin-1'))
                    else:
                        decoded_attributes.append(attribute)
                if indices is not None:
                    decoded_attributes = [decoded_attributes[i] for i in indices]
                if not with_z:
                    yield tuple(record.shape.points[0]), decoded_attributes
                else:
                    if record.shape.shapeType == 11:
                        x, y = record.shape.points[0]
                        z = record.shape.z[0]
                        yield (x, y, z), decoded_attributes
    except error:
        raise ShpException('Error while reading Shapefile. Inconsistent bytes.')


def write_shp_points(output_filename, z_name, points):
    w = shapefile.Writer(shapefile.POINTZ)
    w.field(z_name, 'N', decimal=6)

    for (x, y, z) in points:
        w.point(x, y, z, shapeType=shapefile.POINTZ)
        w.record(z)
    w.save(output_filename)


def write_shp_lines(output_filename, shape_type, lines, attribute_name, m_array=None):
    w = shapefile.Writer(shapeType=shape_type)
    w.field(attribute_name, 'N', decimal=6)

    if m_array is None:
        for poly in lines:
            w.poly(parts=[list(map(tuple, poly.coords()))], shapeType=shape_type)
            w.record(*poly.attributes())
    else:
        for poly, m in zip(lines, m_array):
            coords = np.array(poly.coords())
            if poly.is_2d():
                coords = np.hstack((coords, np.zeros((poly.nb_points(), 1))))
            coords = np.hstack((coords, m))
            w.poly(parts=[list(map(tuple, coords))], shapeType=shape_type)
            w.record(*poly.attributes())
    w.save(output_filename)


class MyWriter(shapefile.Writer):
    """!
    This is a reimplementation of Writer class of pyshp 1.2.11
    The MultiPointZ- and MultiPointM-writing bug is fixed by changing four lines
    see the lines commented with    # HERE GOES THE REIMPLEMENTATION
    Moreover every RuntimeError were replaced by a ShpException
    """
    def __init__(self, shapeType=None):
        super().__init__(shapeType)

    def myshpRecords(self):
        """Write the shp records"""
        f = self.__getFileObj(self.shp)
        f.seek(100)
        recNum = 1
        for s in self._shapes:
            self._offsets.append(f.tell())
            # Record number, Content length place holder
            f.write(pack(">2i", recNum, 0))
            recNum += 1
            start = f.tell()
            # Shape Type
            f.write(pack("<i", s.shapeType))
            # All shape types capable of having a bounding box
            if s.shapeType in (3,5,8,13,15,18,23,25,28,31):
                try:
                    f.write(pack("<4d", *self.__bbox([s])))
                except error:
                    raise ShpException("Failed to write bounding box for record %s. Expected floats." % recNum)
            # Shape types with parts
            if s.shapeType in (3,5,13,15,23,25,31):
                # Number of parts
                f.write(pack("<i", len(s.parts)))
            # Shape types with multiple points per record
            if s.shapeType in (3,5,8,13,15,18,23,25,28,31):   # HERE GOES THE REIMPLEMENTATION
                # Number of points
                f.write(pack("<i", len(s.points)))
            # Write part indexes
            if s.shapeType in (3,5,13,15,23,25,31):
                for p in s.parts:
                    f.write(pack("<i", p))
            # Part types for Multipatch (31)
            if s.shapeType == 31:
                for pt in s.partTypes:
                    f.write(pack("<i", pt))
            # Write points for multiple-point records
            if s.shapeType in (3,5,8,13,15,18,23,25,28,31):   # HERE GOES THE REIMPLEMENTATION
                try:
                    [f.write(pack("<2d", *p[:2])) for p in s.points]
                except error:
                    raise ShpException("Failed to write points for record %s. Expected floats." % recNum)
            # Write z extremes and values
            if s.shapeType in (13,15,18,31):
                try:
                    f.write(pack("<2d", *self.__zbox([s])))
                except error:
                    raise ShpException("Failed to write elevation extremes for record %s. Expected floats." % recNum)
                try:
                    if hasattr(s,"z"):
                        f.write(pack("<%sd" % len(s.z), *s.z))
                    else:
                        [f.write(pack("<d", p[2])) for p in s.points]
                except error:
                    raise ShpException("Failed to write elevation values for record %s. Expected floats." % recNum)
            # Write m extremes and values
            if s.shapeType in (13,15,18,23,25,28,31):
                try:
                    if hasattr(s,"m") and None not in s.m:
                        f.write(pack("<%sd" % len(s.m), *s.m))
                    else:
                        f.write(pack("<2d", *self.__mbox([s])))
                except error:
                    raise ShpException("Failed to write measure extremes for record %s. Expected floats" % recNum)
                try:
                    [f.write(pack("<d", len(p) > 3 and p[3] or 0)) for p in s.points]
                except error:
                    raise ShpException("Failed to write measure values for record %s. Expected floats" % recNum)
            # Write a single point
            if s.shapeType in (1,11,21):
                try:
                    f.write(pack("<2d", s.points[0][0], s.points[0][1]))
                except error:
                    raise ShpException("Failed to write point for record %s. Expected floats." % recNum)
            # Write a single Z value
            if s.shapeType == 11:
                if hasattr(s, "z"):
                    try:
                        if not s.z:
                            s.z = (0,)
                        f.write(pack("<d", s.z[0]))
                    except error:
                        raise ShpException("Failed to write elevation value for record %s. Expected floats." % recNum)
                else:
                    try:
                        if len(s.points[0])<3:
                            s.points[0].append(0)
                        f.write(pack("<d", s.points[0][2]))
                    except error:
                        raise ShpException("Failed to write elevation value for record %s. Expected floats." % recNum)
            # Write a single M value
            if s.shapeType in (11,21):
                if hasattr(s, "m"):
                    try:
                        if not s.m:
                            s.m = (0,)
                        f.write(pack("<1d", s.m[0]))
                    except error:
                        raise ShpException("Failed to write measure value for record %s. Expected floats." % recNum)
                else:
                    try:
                        if len(s.points[0])<4:
                            s.points[0].append(0)
                        f.write(pack("<1d", s.points[0][3]))
                    except error:
                        raise ShpException("Failed to write measure value for record %s. Expected floats." % recNum)
            # Finalize record length as 16-bit words
            finish = f.tell()
            length = (finish - start) // 2
            self._lengths.append(length)
            # start - 4 bytes is the content length field
            f.seek(start-4)
            f.write(pack(">i", length))
            f.seek(finish)

    def myshpFileLength(self):
        """Calculates the file length of the shp file."""
        # Start with header length
        size = 100
        # Calculate size of all shapes
        for s in self._shapes:
            # Add in record header and shape type fields
            size += 12
            # nParts and nPoints do not apply to all shapes
            #if self.shapeType not in (0,1):
            #       nParts = len(s.parts)
            #       nPoints = len(s.points)
            if hasattr(s,'parts'):
                nParts = len(s.parts)
            if hasattr(s,'points'):
                nPoints = len(s.points)
            # All shape types capable of having a bounding box
            if self.shapeType in (3,5,8,13,15,18,23,25,28,31):
                size += 32
            # Shape types with parts
            if self.shapeType in (3,5,13,15,23,25,31):
                # Parts count
                size += 4
                # Parts index array
                size += nParts * 4
            # Shape types with points
            if self.shapeType in (3,5,8,13,15,18,23,25,28,31):   # HERE GOES THE REIMPLEMENTATION
                # Points count
                size += 4
                # Points array
                size += 16 * nPoints
            # Calc size of part types for Multipatch (31)
            if self.shapeType == 31:
                size += nParts * 4
            # Calc z extremes and values
            if self.shapeType in (13,15,18,31):
                # z extremes
                size += 16
                # z array
                size += 8 * nPoints
            # Calc m extremes and values
            if self.shapeType in (15,13,18,23,25,28,31):   # HERE GOES THE REIMPLEMENTATION
                # m extremes
                size += 16
                # m array
                size += 8 * nPoints
            # Calc a single point
            if self.shapeType in (1,11,21):
                size += 16
            # Calc a single Z value
            if self.shapeType == 11:
                size += 8
            # Calc a single M value
            if self.shapeType in (11,21):
                size += 8
        # Calculate size as 16-bit words
        size //= 2
        return size

    def myShapefileHeader(self, fileObj, headerType='shp'):
        """Writes the specified header type to the specified file-like object.
        Several of the shapefile formats are so similar that a single generic
        method to read or write them is warranted."""
        f = self.__getFileObj(fileObj)
        f.seek(0)
        # File code, Unused bytes
        f.write(pack(">6i", 9994,0,0,0,0,0))
        # File length (Bytes / 2 = 16-bit words)
        if headerType == 'shp':
            f.write(pack(">i", self.myshpFileLength()))
        elif headerType == 'shx':
            f.write(pack('>i', ((100 + (len(self._shapes) * 8)) // 2)))
        # Version, Shape type
        f.write(pack("<2i", 1000, self.shapeType))
        # The shapefile's bounding box (lower left, upper right)
        if self.shapeType != 0:
            try:
                f.write(pack("<4d", *self.bbox()))
            except error:
                raise ShpException("Failed to write shapefile bounding box. Floats required.")
        else:
            f.write(pack("<4d", 0,0,0,0))
        # Elevation
        z = self.zbox()
        # Measure
        m = self.mbox()
        try:
            f.write(pack("<4d", z[0], z[1], m[0], m[1]))
        except error:

            raise ShpException("Failed to write shapefile elevation and measure values. Floats required.")

    def __getFileObj(self, f):
        """Safety handler to verify file-like objects"""
        if not f:
            raise ShpException("No file-like object available.")
        elif hasattr(f, "write"):
            return f
        else:
            pth = os.path.split(f)[0]
            if pth and not os.path.exists(pth):
                os.makedirs(pth)
            return open(f, "wb")

    def __bbox(self, shapes):
        x = []
        y = []
        for s in shapes:
            if len(s.points) > 0:
                px, py = list(zip(*s.points))[:2]
                x.extend(px)
                y.extend(py)
        if len(x) == 0:
            return [0] * 4
        return [min(x), min(y), max(x), max(y)]

    def __zbox(self, shapes):
        z = []
        for s in shapes:
            try:
                for p in s.points:
                    z.append(p[2])
            except IndexError:
                pass
        if not z: z.append(0)
        return [min(z), max(z)]

    def __mbox(self, shapes):
        m = []
        for s in shapes:
            try:
                for p in s.points:
                    m.append(p[3])
            except IndexError:
                pass
        if not m: m.append(0)
        return [min(m), max(m)]

    def saveShp(self, target):
        """Save an shp file."""
        if not hasattr(target, "write"):
            target = os.path.splitext(target)[0] + '.shp'
        self.shp = self.__getFileObj(target)
        self.myShapefileHeader(self.shp, headerType='shp')
        self.myshpRecords()
