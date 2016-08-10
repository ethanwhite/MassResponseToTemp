from __future__ import division
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd
import numpy as np
import calendar
from osgeo import gdal
import statsmodels.formula.api as smf

def create_month_codes_dict(jan_code, dec_code, diff):
    """Create dictionary of month names and corresponding codes
    
    Args: 
        jan_code: Code corresponding to month of January
        dec_code: Code corresponding to month of December
        diff: What value to add/subtract between each month code
    
    Returns: 
        Dictionary of month names and codes
    """
    month_names = []
    for each_month in range(1, 13):
        month_names.append(calendar.month_name[each_month])
    codes = range(jan_code, dec_code, diff)
    month_codes = {}
    for month, code in zip(month_names, codes):
        month_codes[month] = code
    return month_codes

def get_stackID(year, month_code):
    """Get stackID for chosen month and year
    
    Args:
        year: Year for stackID
        month_code: Code for chosen month
    
    Returns:
        StackID for month and year
    """
    stackID = year * 12 - month_code
    return stackID


def get_temps_list(coordinates, bands): 
    """Get temperatures for lists of locations and stackIDs
    
    Args: 
        raster_file: File of temperatures
        coordinates: Dataframe columns with location coordinates
        band: Dataframe column with stackID corresponding to desired month and year
    
    Returns: 
        List of temperatures for coordinates and stackIDs
    """
    open_file = gdal.Open(temp_file) #add raster file back in as argument
    all_temps = []
    for i in range(len(bands)): 
        single_band = open_file.GetRasterBand(bands.iloc[i])
        geotrans_raster = open_file.GetGeoTransform()
        x = int((coordinates.iloc[i][0] - geotrans_raster[0])/geotrans_raster[1])
        y = int((coordinates.iloc[i][1] - geotrans_raster[3])/geotrans_raster[5])
        band_array = single_band.ReadAsArray()
        packed_temp = band_array[y, x]
        add_offset = single_band.GetOffset()
        scale_factor = single_band.GetScale()
        unpacked_temp = add_offset + (packed_temp * scale_factor)
        all_temps.append(unpacked_temp)
    open_file = None
    return all_temps

def remove_species(dataframe, species_col): 
    """Remove species from dataframe that have fewer than 30 individuals due to
    a lack of temperature data
    
    Args: 
        dataframe: initial dataframe
        species_col: column that contains species names
    
    Returns: 
        Dataframe that contains species with >30 individuals
    
    """
    insufficient_species = []
    for species, species_data in dataframe.groupby(species_col): 
        if len(species_data["row_index"].unique()) < 30: 
            insufficient_species.append(species)
    sufficient_species_df = dataframe[dataframe[species_col].isin(insufficient_species) == False]
    return sufficient_species_df

def lin_reg(dataset, speciesID_col): 
    temp_pdf = PdfPages("results/temp_currentyear.pdf")
    lat_pdf = PdfPages("results/lat.pdf")
    stats_list = []
    for species, species_data in dataset.groupby(speciesID_col): 
        sp_class = species_data["class"].unique()
        sp_class = sp_class[0]
        #TODO: remove nan from class
        #sp_class = sp_class[~np.isnan(sp_class)]
        temp_linreg = smf.ols(formula = "mass ~ july_temps", data = species_data).fit()
        plt.figure()
        plt.plot(species_data["july_temps"], species_data["mass"], "bo")
        plt.plot(species_data["july_temps"], temp_linreg.fittedvalues, "r-")
        plt.xlabel("Current year temperature")
        plt.ylabel("Mass(g)")
        plt.suptitle(species)
        temp_pdf.savefig()
        plt.close()
        if species_data["decimallatitude"].mean() < 0: 
            hemisphere = "south"
        else: 
            hemisphere = "north"
        lat_linreg = smf.ols(formula = "mass ~ abs(decimallatitude)", data = species_data).fit()
        plt.figure()
        plt.plot(abs(species_data["decimallatitude"]), species_data["mass"], "bo")
        plt.plot(abs(species_data["decimallatitude"]), lat_linreg.fittedvalues, "r-")
        plt.xlabel("Latitude")
        plt.ylabel("Mass(g)")
        plt.title(species)
        plt.figtext(0.05, 0.05, hemisphere)
        lat_pdf.savefig()
        plt.close()     
        stats_list.append({"genus_species": species, "class": sp_class, "individuals": len(species_data["row_index"].unique()),  "hemisphere": hemisphere, "temp_r_squared": temp_linreg.rsquared, "temp_slope": temp_linreg.params[1], "lat_r_squared": lat_linreg.rsquared, "lat_slope": lat_linreg.params[1]})    
    temp_pdf.close()
    lat_pdf.close()
    stats_df = pd.DataFrame(stats_list)
    return stats_df

# Datasets
individual_data = pd.read_csv("CompleteDatasetVN.csv", usecols = ["row_index", "clean_genus_species", "class", "year", "longitude", "decimallatitude", "mass"])
#full_individual_data = pd.read_csv("CompleteDatasetVN.csv", usecols = ["row_index", "clean_genus_species", "class", "year", "longitude", "decimallatitude", "mass"])
#species_list = full_individual_data["clean_genus_species"].unique().tolist()
#species_list = sorted(species_list)
#individual_data = full_individual_data[full_individual_data["clean_genus_species"].isin(species_list[1303:1310])]

gdal.AllRegister()
driver = gdal.GetDriverByName("netCDF")
temp_file = "air.mon.mean.v301.nc"

# List of months with corresponding stackID codes
month_codes = create_month_codes_dict(22799, 22787, -1)

# Get stackIDs for July and year
individual_data["stackID_july"] = get_stackID(individual_data["year"], month_codes["July"])

# Avoiding multiple temp lookups for same location/year combinations
temp_lookup = individual_data[["longitude", "decimallatitude", "stackID_july"]]
temp_lookup = temp_lookup.drop_duplicates()

# Get temperatures for July
temp_lookup["july_temps"] = get_temps_list(temp_lookup[["longitude", "decimallatitude"]], temp_lookup["stackID_july"])
temp_data = individual_data.merge(temp_lookup)

# Remove rows with missing data values (i.e., 3276.7)
temp_data = temp_data[temp_data["july_temps"] < 3276]

# Remove species with less than 30 individuals
stats_data = remove_species(temp_data, "clean_genus_species")

# Linear regression for temp and latitude for all species, both plots and df
species_stats = lin_reg(stats_data, "clean_genus_species")
species_stats.to_csv("results/species_stats.csv")
stats_data.to_csv("results/stats_data.csv")