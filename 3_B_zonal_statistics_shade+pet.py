#import data
import geopandas as gpd
import pandas as pd
import osmnx as ox
import numpy as np
import rasterio
import rasterio.mask
import shapely
import fiona
from tqdm.asyncio import tqdm
import exactextract

# Define constants
root_folder = "./root"
buffer_distance = 10
adjustment_curve = pd.read_csv(f"{root_folder}/Inputs/adjustment_curve.csv")

# Load the virtual raster dataset with all the shade and PET rasters in different bands
virt_raster = rasterio.open(f"{root_folder}/Masked/merged.vrt")

# Get the number of bands in the virtual raster
n_bands = virt_raster.count
print(f"Virtual raster has {n_bands} bands.")

# Load the walking network with the common code
area_shape = fiona.open(f"{root_folder}/Inputs/GemeenteAmsterdam.geojson")
area_shape = shapely.geometry.shape(area_shape[0]['geometry'])

cf = """
     ["area"!~"yes"]
     ["highway"]
     ["highway"!~"motor|proposed|construction|abandoned|platform|raceway"]
     ["foot"!~"no"]
     ["service"!~"private"]
     ["access"!~"private"]
     """

G = ox.graph_from_polygon(polygon=area_shape, custom_filter=cf, simplify=False, retain_all=True, network_type="walk", truncate_by_edge=True)

# Convert to GeoDataFrame
gdf = ox.graph_to_gdfs(G, nodes=False, edges=True,  node_geometry=False, fill_edge_geometry=True)
gdf.to_crs("EPSG:28992", inplace=True)

# Draw a buffer around the edges in the network, pass along the u and v data of the edge.
buffer_gs = gdf.buffer(buffer_distance)

# Replace the geometry of the edges with the buffered geometry
gdf['geometry'] = buffer_gs

# Run zonal statistics on the virtual raster dataset
zonal_stats = exactextract.exact_extract(
    rast = virt_raster, 
    vec = gdf, 
    ops = 'mean',
    output = "pandas",
    include_geom=True,
    progress = True
)

# Save the zonal statistics to a file
zonal_stats.to_file(f"{root_folder}/Outputs/zonal_stats.geojson", driver='GeoJSON')

# Add the values to the original gdf
gdf = ox.graph_to_gdfs(G, nodes=False, edges=True,  node_geometry=False, fill_edge_geometry=True)
gdf = gdf.reset_index()

# Create columns for each time interval
time_intervals = [f"{hour:02d}{minute:02d}" for hour in range(9, 21) for minute in (0, 30)]
time_intervals.pop()
for i, time_interval in enumerate(time_intervals, start=1):
    gdf[f'{time_interval}'] = zonal_stats[f'band_{i}_mean']
gdf['PET'] = zonal_stats['band_24_mean']


# Save the gdf to a file
gdf.to_file(f"{root_folder}/Outputs/edges_zonalstats.gpkg", driver='GPKG', layer='shade+pet')
gdf = gpd.read_file(f"{root_folder}/Outputs/edges_zonalstats.gpkg", layer='shade+pet')

# Define a function to get the adjusted sum
def get_adjusted_sum(row, time_intervals):
    return sum([row[time_interval] * adjustment_curve[time_interval].iloc[0] for time_interval in time_intervals])

# Then apply it to create the new column
tqdm.pandas()
gdf = gdf.assign(sum_adjust=lambda x: x.progress_apply(
    lambda row: get_adjusted_sum(row, time_intervals), 
    axis=1
))

# Create a new column with the average exposure between 11 and 17
time_intervals = [f"{hour:02d}{minute:02d}" for hour in range(11, 18) for minute in (0, 30)]
time_intervals.pop()

# Define a function to get the average
def get_avg(row, time_intervals):
    return np.average([row[time_interval] for time_interval in time_intervals])

# Then apply it to create the new column, and do the same but inverted for shade
tqdm.pandas()
gdf = gdf.assign(avg_exposure_percent=lambda x: x.progress_apply(
    lambda row: get_avg(row, time_intervals), 
    axis=1
))
gdf = gdf.assign(avg_shade_percent=lambda x: x.progress_apply(
    lambda row: 1 - get_avg(row, time_intervals), 
    axis=1
))

# Save the gdf with the sum and averages to a file
gdf.to_file(f"{root_folder}/Outputs/3_Shade+PET.gpkg", driver='GPKG', layer='shade+pet')