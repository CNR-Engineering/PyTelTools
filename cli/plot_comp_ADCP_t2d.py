#!/usr/bin/env python

"""
Plot ADCP and TELEMAC velocity and compute RMSE
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
import os

from pyteltools.utils.cli_base import PyTelToolsArgParse


def plot_comp_ADCP_t2d(args):

    ADCP = pd.read_csv(args.inADCP, sep=';', header=0)

    ADCP['Distance_pts'] =np.nan

    for y in range(len(ADCP["X"])):
        if(y == 0):
            ADCP["Distance_pts"][0] = 0
        else:
            ADCP["Distance_pts"][y] = np.sqrt( ((ADCP['X'][y]-ADCP['X'][y-1])**2) + ((ADCP['Y'][y]-ADCP['Y'][y-1])**2))

    ADCP['Distance'] = ADCP['Distance_pts'].cumsum(axis = 0)
    grid = np.arange(0,float(ADCP["Distance"][-1:]), int(float(ADCP["Distance"][-1:]))/args.Numberdiv)
    grid = np.append(grid,float(ADCP["Distance"][-1:]))
    file_df_mean = pd.DataFrame()
    file_df_mean["Distance"] = grid
    Mean_vel = []

    fig, axs = plt.subplots(2)


    for i in range(len(grid)):
        if(i == 0):
            Mean_vel.append(ADCP['MagnitudeXY'][0])
        else:
            Magnitude = []
            Distance = []
            Distance_pts = []
            Distance_pts_cum = []
            mean = []
            Distance.append(grid[i -1])
            Magnitude.append(np.interp(grid[i - 1], ADCP['Distance'], ADCP['MagnitudeXY']))

            Distance.extend(ADCP['Distance'][((np.where(ADCP['Distance'] >= grid[i - 1]))[0][0]): (
                    (np.where(ADCP['Distance'] >= grid[i]))[0][0] - 1)])
            Magnitude.extend(ADCP['MagnitudeXY'][((np.where(ADCP['Distance'] >= grid[i - 1]))[0][0]): (
                        (np.where(ADCP['Distance'] >= grid[i]))[0][0] - 1)])

            Distance.append(grid[i])
            Magnitude.append(np.interp(grid[i], ADCP['Distance'], ADCP['MagnitudeXY']))
            Distance_pts.append(0)
            Distance_pts.extend( [Distance[x+1] - Distance[x] for x in range(0, len(Distance)-1)] )
            Distance_pts_cum.extend(np.cumsum(Distance_pts))
            mean.extend([a*b for a,b in zip(Distance_pts,Magnitude)])
            Mean_vel.append(sum(mean) / Distance_pts_cum[-1])

    file_df_mean["MagnitudeXY"] = Mean_vel
    axs[0].plot(file_df_mean['Distance'], file_df_mean['MagnitudeXY'], label=("Mean_ADCP"))
    axs[0].scatter(ADCP['Distance'], ADCP['MagnitudeXY'], label="ADCP")

    data_t2d = pd.read_csv(args.inT2DCSV, sep=';')
    col_labels = list(np.unique(data_t2d['folder']))
    RMSE = []
    for col in col_labels:
        file_df = data_t2d[data_t2d['folder'] == col]
        #axs[0].scatter(file_df['Distance'],file_df['value'],label = os.path.basename(os.path.dirname(dirfor)))
        file_df_mean_TEL = pd.DataFrame()
        file_df_mean_TEL["distance"] = grid
        Mean_vel = []
        for i in range(len(grid)):
            Magnitude = []
            Distance = []
            Distance_pts = []
            Distance_pts_cum = []
            mean = []
            Distance.append(grid[i-1])
            Magnitude.append(np.interp(grid[i-1], file_df['distance'], file_df['value']))

            #Distance.extend(file_df['Distance'][((np.where(file_df['Distance'] >= grid[i-1]))[0][0]): (
            #(np.where(file_df['Distance'] >= grid[i]))[0][0] - 1)])
            #Magnitude.extend(file_df['value'][((np.where(file_df['Distance'] >= grid[i-1]))[0][0]): (
            #        (np.where(file_df['Distance'] >= grid[i]))[0][0] - 1)])
            Distance.append(grid[i])
            Magnitude.append(np.interp(grid[i], file_df['distance'], file_df['value']))
            Distance_pts.append(0)
            Distance_pts.extend([Distance[x + 1] - Distance[x] for x in range(0, len(Distance) - 1)])
            Distance_pts_cum.extend(np.cumsum(Distance_pts))
            mean.extend([a * b for a, b in zip(Distance_pts, Magnitude)])
            Mean_vel.append(sum(mean) / Distance_pts_cum[-1])
        file_df_mean_TEL["value"] = Mean_vel
        axs[0].plot(file_df_mean_TEL['distance'], file_df_mean_TEL['value'], label=("Mean"+col))
        RMSE.append(np.sqrt(((file_df_mean['MagnitudeXY'] - file_df_mean_TEL['value'])**2).mean()))

    axs[1].bar(col_labels,RMSE)
    axs[1].set_ylabel('Root Mean Square error')
    axs[0].set_xlabel('Distance [m]')
    axs[0].set_ylabel('Vitesse [m/s]')
    box = axs[0].get_position()
    axs[0].set_position([box.x0, box.y0, box.width * 0.8, box.height])
    axs[0].legend(loc='center left', bbox_to_anchor=(1, 0.5))
    fig.set_size_inches(18.5, 10.5)
    plt.savefig(args.outGraph)
    plt.show()


parser = PyTelToolsArgParse(description=__doc__)
parser.add_argument("inADCP", help="ADCP (.csv) input filename")
parser.add_argument("inT2DCSV", help="List of folder containing (.csv) files")
parser.add_argument("--Numberdiv", help="Segments number of the line to compute average velocity on a normal grid",
                    default=10)
parser.add_argument("outGraph", help="Filename of plot (.png)")


if __name__ == "__main__":
    args = parser.parse_args()
    plot_comp_ADCP_t2d(args)
