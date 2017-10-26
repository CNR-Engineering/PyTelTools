from datetime import datetime
from PyQt5.QtWidgets import *
from workflow.MultiNode import MultiNode, MultiOneInOneOutNode, MultiSingleInputNode, \
                               MultiSingleOutputNode, MultiDoubleInputNode, MultiTwoInOneOutNode
from workflow.util import MultiLoadSerafinDialog, validate_output_options, validate_input_options
from slf.Serafin import SLF_EIT
from slf.variables import get_US_equation
import slf.misc as operations
from geom.transformation import load_transformation_map


class MultiLoadSerafin2DNode(MultiSingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load\nSerafin 2D'
        self.state = MultiNode.NOT_CONFIGURED

    def configure(self, old_options):
        dlg = MultiLoadSerafinDialog(old_options)
        if dlg.exec_() == QDialog.Accepted:
            if dlg.success:
                self.state = MultiNode.READY
                return True, [dlg.dir_paths, dlg.slf_name, dlg.job_ids]
        return False, []


class MultiLoadSerafin3DNode(MultiSingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load\nSerafin 3D'
        self.state = MultiNode.NOT_CONFIGURED

    def configure(self, old_options):
        dlg = MultiLoadSerafinDialog(old_options)
        if dlg.exec_() == QDialog.Accepted:
            if dlg.success:
                self.state = MultiNode.READY
                return True, [dlg.dir_paths, dlg.slf_name, dlg.job_ids]
        return False, []


class MultiWriteSerafinNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Write\nSerafin'

    def load(self, options):
        success, self.options = validate_output_options(options)
        if not success:
            self.state = MultiNode.NOT_CONFIGURED


class MultiLoadPolygon2DNode(MultiSingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load 2D\nPolygons'

    def load(self, options):
        success, filename = validate_input_options(options)
        if not success:
            self.state = MultiNode.NOT_CONFIGURED
        self.options = filename,


class MultiLoadOpenPolyline2DNode(MultiSingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load 2D\nOpen\nPolylines'

    def load(self, options):
        success, filename = validate_input_options(options)
        if not success:
            self.state = MultiNode.NOT_CONFIGURED
        self.options = filename,


class MultiLoadPoint2DNode(MultiSingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load 2D\nPoints'

    def load(self, options):
        success, filename = validate_input_options(options)
        if not success:
            self.state = MultiNode.NOT_CONFIGURED
        self.options = filename,


class MultiLoadReferenceSerafinNode(MultiSingleOutputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Load\nReference\nSerafin'

    def load(self, options):
        success, filename = validate_input_options(options)
        if not success:
            self.state = MultiNode.NOT_CONFIGURED
        self.options = filename,


class MultiWriteLandXMLNode(MultiSingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Write\nLandXML'

    def load(self, options):
        success, self.options = validate_output_options(options)
        if not success:
            self.state = MultiNode.NOT_CONFIGURED


class MultiWriteShpNode(MultiSingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Write shp'

    def load(self, options):
        success, self.options = validate_output_options(options)
        if not success:
            self.state = MultiNode.NOT_CONFIGURED


class MultiWriteVtkNode(MultiSingleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Input/Output'
        self.label = 'Write vtk'

    def load(self, options):
        success, self.options = validate_output_options(options)
        if not success:
            self.state = MultiNode.NOT_CONFIGURED


class MultiAddTransformationNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Add\nTransformation'

    def load(self, options):
        filename, from_index, to_index = options
        if not filename:
            return
        try:
            with open(filename) as f:
                pass
        except FileNotFoundError:
            self.state = MultiNode.NOT_CONFIGURED
            return
        success, transformation = load_transformation_map(filename)
        if not success:
            self.state = MultiNode.NOT_CONFIGURED
            return
        from_index, to_index = int(from_index), int(to_index)
        if from_index not in transformation.nodes or to_index not in transformation.nodes:
            self.state = MultiNode.NOT_CONFIGURED
            return
        trans = transformation.get_transformation(from_index, to_index)
        self.options = (trans,)


class MultiConvertToSinglePrecisionNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Convert to\nSingle\nPrecision'


class MultiComputeMaxNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Max'


class MultiArrivalDurationNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Compute\nArrival\nDuration'

    def load(self, options):
        table = []
        conditions = []
        str_conditions, str_table, time_unit = options
        str_table = str_table.split(',')
        for i in range(int(len(str_table)/3)):
            line = []
            for j in range(3):
                line.append(str_table[3*i+j])
            table.append(line)
        if not table:
            self.state = MultiNode.NOT_CONFIGURED
            return
        str_conditions = str_conditions.split(',')
        for i, condition in zip(range(len(table)), str_conditions):
            literal = table[i][0]
            condition = condition.split()
            expression = condition[:-2]
            comparator = condition[-2]
            threshold = float(condition[-1])
            conditions.append(operations.Condition(expression, literal, comparator, threshold))
        self.options = (table, conditions, time_unit)


class MultiComputeVolumeNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Compute\nVolume'

    def load(self, options):
        first, second, sup = options[0:3]
        if first:
            first_var = first
        else:
            self.state = MultiNode.NOT_CONFIGURED
            return
        if second:
            second_var = second
        else:
            second_var = None
        sup_volume = bool(int(sup))
        success, (suffix, in_source_folder, dir_path, double_name, overwrite) = validate_output_options(options[3:])
        if not success:
            self.state = MultiNode.NOT_CONFIGURED
            return
        self.options = (first_var, second_var, sup_volume, suffix, in_source_folder, dir_path, double_name, overwrite)


class MultiComputeFluxNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Compute\nFlux'

    def load(self, options):
        flux_options = options[0]
        if not flux_options:
            self.state = MultiNode.NOT_CONFIGURED
            return
        success, (suffix, in_source_folder, dir_path, double_name, overwrite) = validate_output_options(options[1:])
        if not success:
            self.state = MultiNode.NOT_CONFIGURED
            return
        self.options = (flux_options, suffix, in_source_folder, dir_path, double_name, overwrite)


class MultiInterpolateOnPointsNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Interpolate\non\nPoints'

    def load(self, options):
        success, self.options = validate_output_options(options)
        if not success:
            self.state = MultiNode.NOT_CONFIGURED


class MultiInterpolateAlongLinesNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Interpolate\nalong\nLines'

    def load(self, options):
        success, self.options = validate_output_options(options)
        if not success:
            self.state = MultiNode.NOT_CONFIGURED


class MultiProjectLinesNode(MultiDoubleInputNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Calculations'
        self.label = 'Project\nLines'

    def load(self, options):
        success, (suffix, in_source_folder, dir_path, double_name, overwrite) = validate_output_options(options[:5])
        if not success:
            self.state = MultiNode.NOT_CONFIGURED
            return
        reference_index = int(options[5])
        if reference_index == -1:
            self.state = MultiNode.NOT_CONFIGURED
            return
        self.options = (suffix, in_source_folder, dir_path, double_name, overwrite, reference_index)


class MultiComputeMinNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Min'


class MultiComputeMeanNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Mean'


class MultiSynchMaxNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'SynchMax'

    def load(self, options):
        self.options = (options[0],)


class MultiSelectFirstFrameNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nFirst\nFrame'


class MultiSelectLastFrameNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nLast\nFrame'


class MultiSelectTimeNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nTime'

    def load(self, options):
        str_start_date, str_end_date = options[0:2]
        if not str_start_date:
            self.state = MultiNode.NOT_CONFIGURED
            return
        start_date = datetime.strptime(str_start_date, '%Y/%m/%d %H:%M:%S')
        end_date = datetime.strptime(str_end_date, '%Y/%m/%d %H:%M:%S')
        sampling_frequency = int(options[2])
        self.options = (start_date, end_date, sampling_frequency)


class MultiSelectSingleFrameNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nSingle\nFrame'

    def load(self, options):
        str_date = options[0]
        if not str_date:
            self.state = MultiNode.NOT_CONFIGURED
            return
        self.options = (datetime.strptime(str_date, '%Y/%m/%d %H:%M:%S'),)


class MultiSelectSingleLayerNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nSingle\nLayer'

    def load(self, options):
        layer_selection = int(options[0])
        if layer_selection<=0:
            self.state = MultiNode.NOT_CONFIGURED
            return
        self.options = (layer_selection,)


class MultiSelectVariablesNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Select\nVariables'

    def load(self, options):
        friction_law, vars, names, units = options
        friction_law = int(friction_law)
        if friction_law > -1:
            us_equation = get_US_equation(friction_law)
        else:
            us_equation = None

        if not vars:
            self.state = MultiNode.NOT_CONFIGURED
            return

        selected_vars = []
        selected_vars_names = {}
        for var, name, unit in zip(vars.split(','), names.split(','), units.split(',')):
            selected_vars.append(var)
            selected_vars_names[var] = (bytes(name, SLF_EIT).ljust(16), bytes(unit, SLF_EIT).ljust(16))
        self.options = (us_equation, selected_vars, selected_vars_names)


class MultiAddRouseNode(MultiOneInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Basic operations'
        self.label = 'Add\nRouse'

    def load(self, options):
        values, str_table = options
        str_table = str_table.split(',')
        table = []
        if not values:
            self.state = MultiNode.NOT_CONFIGURED
            return
        for i in range(0, len(str_table), 3):
            table.append([str_table[i], str_table[i+1], str_table[i+2]])
        self.options = (table,)


class MultiMinusNode(MultiTwoInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'A Minus B'


class MultiReverseMinusNode(MultiTwoInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'B Minus A'


class MultiProjectMeshNode(MultiTwoInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Project B\non A'


class MultiMaxBetweenNode(MultiTwoInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Max(A,B)'


class MultiMinBetweenNode(MultiTwoInOneOutNode):
    def __init__(self, index):
        super().__init__(index)
        self.category = 'Operators'
        self.label = 'Min(A,B)'

