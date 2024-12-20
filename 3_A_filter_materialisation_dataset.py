import geopandas as gpd
import shapely
import pyproj
from shapely.ops import transform


#Define constants
root_folder = "./root"
bbox = [52.43, 52.28, 5.10, 4.74] #N,S,E,W  #Amsterdam
bbox_xyxy = [bbox[3], bbox[1], bbox[2], bbox[0]] #W,S,E,N

# Create bounding box with correct coordinate order (minx, miny, maxx, maxy)
# bbox format is [N, S, E, W] = [max_lat, min_lat, max_lon, min_lon]
bounding_box_shape = shapely.box(
    xmin=bbox[3],  # W longitude
    ymin=bbox[1],  # S latitude
    xmax=bbox[2],  # E longitude 
    ymax=bbox[0]   # N latitude
)

# Create transformer with always_xy=True to handle coordinate ordering
project = pyproj.Transformer.from_crs(
    "EPSG:4326",    # WGS84
    "EPSG:28992",   # Dutch RD New
    always_xy=True  # Ensures lon/lat (x/y) ordering
)

# Transform the geometry
bounding_box_shape_RDNew = transform(project.transform, bounding_box_shape)


# Import the materialisation data into a geodataframe
gdf = gpd.read_file(f"{root_folder}/Inputs/materialisation.gpkg") #! Make sure that CRS is the same as raster datasets.

# Filter for non-road paths (first condition group)
path_filter = gdf['Gebruiksfunctie'].isin([
    'Fietspad', 'Halte eiland', 'Ruiterpad', 'Speelondergrond',
    'Verkeerseiland', 'Voetgangersgebied', 'Voetpad', 
    'Voetpad op trap', 'Winkelerf', 'Woonerf'
])

# Filter for Rijbaan with specific Types
road_type_filter = (
    (gdf['Gebruiksfunctie'] == 'Rijbaan') & 
    (gdf['Type'].isin([
        'Elementenverharding', 'Halfverharding',
        'Kunststofverharding', 'Onverhard'
    ]))
)

# Combine filters: path_filter OR (road_filter AND type_filter)
filtered_gdf = gdf[path_filter | road_type_filter]
print(f"Filtered {len(gdf) - len(filtered_gdf)} rows from the materialisation data.")

# Buffer all the polygons by 0.2 meters to remove gaps
filtered_gdf['geometry'] = filtered_gdf.buffer(0.2)

# Clip all polygons to the bounding box
filtered_gdf = filtered_gdf.clip(bounding_box_shape_RDNew)

# Dissolve the filtered geodataframe
filtered_gdf = filtered_gdf.dissolve()
filtered_gdf = filtered_gdf.explode()
print(f"Filtered geodataframe has {len(filtered_gdf)} rows.")

# Save the filtered geodataframe to a file
filtered_gdf.to_file(f"{root_folder}/Masked/filtered_materialisation.gpkg", driver='GPKG')

# Remove gdf from memory
del filtered_gdf
del gdf

print(f"""
      Filtered materialisation data saved to file: {root_folder}/Masked/filtered_materialisation.gpkg
      The raster datasets must be masked with the filtered materialisation data.
      We advise to do this in QGIS or another GIS software for efficiency.
      Also note that for the zonal statistics, the filtered raster datasets must be combined into one virtual raster .vrt file.
      The last band in the virtual raster should be the PET raster.
      """)

