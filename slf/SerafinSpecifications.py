# -*- coding: utf-8 -*-

import os
import pandas as pd


class SerafinVariableNames:
    """
    manage variables names (fr/eng): loading, adding and removing
    """
    def __init__(self, is_2d, language):
        self.language = language
        base_folder = os.path.dirname(os.path.realpath(__file__))
        if is_2d:
            self.var_table = pd.read_csv(os.path.join(base_folder, 'data', 'Serafin_var2D.csv'),
                                         index_col=0, header=0, sep=',')
        else:
            self.var_table = pd.read_csv(os.path.join(base_folder, 'data', 'Serafin_var3D.csv'),
                                         index_col=0, header=0, sep=',')

    def name_to_ID(self, var_name):
        """
        @brief: Assign an ID to variable name
        @param var_name <bytes>: the name of the new variable
        @return var_ID <bytes> the unit of the new variable
        """
        try:
            var_index = self.var_table[self.language].tolist().index(var_name)
        except ValueError:
            return  # handled in Serafin.Read
        var_ID = self.var_table.index.values[var_index]
        return var_ID

    def add_new_var(self, var_name, var_unit):
        """
        @brief: Add new variable specification in the table
        @param var_name <bytes>: the name of the new variable
        @param var_unit <bytes> the unit of the new variable
        """
        self.var_table.append({var_name.decode('utf-8'): [var_name, var_name, var_unit]}, ignore_index=True)

    def ID_to_name_unit(self, var_ID):
        var_row = self.var_table.loc[var_ID]
        return bytes(var_row[self.language], 'utf-8'), bytes(var_row['unit'], 'utf-8')




