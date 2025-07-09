import bpy
import csv
import math
from mathutils import Vector
import os # For getting base name of the model file

# --- Configuration ---
# csv_file_path is now a parameter to run_visualization

# Default column names - these can also be customized per run_visualization call
DEFAULT_DATA_COLUMN_NAME = "GDP"
DEFAULT_CATEGORY_COLUMN_NAME = "Country"
DEFAULT_POPULATION_COLUMN_NAME = "Population"

USE_LINEAR_SCALING = True
MIN_VISUAL_SCALE = 5.0
MAX_VISUAL_SCALE = 300.0
SCALING_POWER = 1.5

PROPORTIONAL_GAP_FACTOR = 0.5
MIN_CLEARANCE_BETWEEN_MODELS = 2.0

MODEL_COLOR = (0.8, 0.2, 0.1, 1.0)

# New: Target base dimension for the source model before data-driven scaling
# This ensures all source models start with a consistent horizontal footprint.
TARGET_BASE_DIMENSION = 1.0 # e.g., 1 unit for the largest horizontal dimension

# --- Batching Configuration ---
BATCH_SIZE = 10  # Number of models to process per batch
BATCH_DELAY_SECONDS = 0.01  # Delay between batches (can be 0 for responsiveness without explicit pause)

# --- Global variables for batching (simplified and now passed via a context dict) ---
_batch_context = {}

# --- Helper Functions ---

def get_or_create_collection(parent_collection, collection_name):
    """Gets an existing collection or creates a new one and links it to parent."""
    if collection_name in bpy.data.collections:
        collection = bpy.data.collections[collection_name]
    else:
        collection = bpy.data.collections.new(collection_name)
        parent_collection.children.link(collection)
    return collection

def clear_script_generated_elements(root_collection_name):
    """
    Deletes all objects and collections under the specified root_collection_name,
    which are created by this script. Leaves all other collections and their contents untouched.
    """
    bpy.ops.object.select_all(action='DESELECT')

    if root_collection_name not in bpy.data.collections:
        print(f"Root visualization collection '{root_collection_name}' not found for cleanup. Skipping.")
        return

    root_coll = bpy.data.collections[root_collection_name]

    objects_to_delete = []
    collections_to_delete = []

    def collect_for_deletion(collection):
        for obj in collection.objects:
            objects_to_delete.append(obj)
        for child_coll in collection.children:
            collect_for_deletion(child_coll)
            collections_to_delete.append(child_coll)

    collect_for_deletion(root_coll)
    collections_to_delete.append(root_coll)

    if objects_to_delete:
        for obj in objects_to_delete:
            for coll in obj.users_collection:
                if coll.name in [c.name for c in collections_to_delete]:
                    coll.objects.unlink(obj)
            bpy.data.objects.remove(obj, do_unlink=True)
        print(f"Deleted {len(objects_to_delete)} objects from '{root_collection_name}'.")
    else:
        print(f"No objects found to delete in '{root_collection_name}'.")

    for collection in reversed(collections_to_delete):
        if collection.name in bpy.data.collections:
            bpy.data.collections.remove(collection)
            print(f"Removed collection: {collection.name}")

    mats_to_remove = []
    for mat in bpy.data.materials:
        is_used = False
        for mesh in bpy.data.meshes:
            if mat in mesh.materials:
                is_used = True
                break
        if not is_used and mat.name.startswith("Model_Material"):
            mats_to_remove.append(mat)
    
    for mat in mats_to_remove:
        bpy.data.materials.remove(mat)
        print(f"Removed unused material: {mat.name}")

    print("Scene cleanup completed for script-generated elements.")

def parse_csv_data(file_path, data_column_name, category_column_name, population_column_name):
    """Parses CSV data, specifically looking for specified columns."""
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file)
            if data_column_name not in reader.fieldnames:
                print(f"Error: Data column '{data_column_name}' not found in CSV.")
                return []
            if category_column_name not in reader.fieldnames:
                print(f"Error: Category column '{category_column_name}' not found in CSV.")
                return []
            if population_column_name not in reader.fieldnames:
                print(f"Warning: Population column '{population_column_name}' not found in CSV. Using N/A.")

            for i, row in enumerate(reader):
                try:
                    data_value = float(row.get(data_column_name, 0.0))
                    category_name = row.get(category_column_name, f"Unknown {category_column_name} {i+1}")
                    population_value = int(row.get(population_column_name, 0)) if population_column_name in row else 'N/A'

                    data.append({
                        'ID': int(row.get('ID', i)),
                        'Category': category_name,
                        'Population': population_value,
                        'DataValue': data_value
                    })
                except (ValueError, KeyError) as e:
                    print(f"Skipping row {i+2} due to parsing error: {e}. Row data: {row}")
            data.sort(key=lambda x: x['DataValue'])
            print(f"✅ Successfully read {len(data)} data points from CSV.")
            return data
    except FileNotFoundError:
        print(f"Error: CSV file not found at '{file_path}'.")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while reading CSV file: {e}")
        return []

def get_bounding_box_dimensions(obj):
    """Returns the width, depth, and height of an object's bounding box in world space."""
    bpy.context.view_layer.update()
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    xs = [v.x for v in bbox_corners]
    ys = [v.y for v in bbox_corners]
    zs = [v.z for v in bbox_corners]
    return max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)

def get_combined_bounding_box_world(objects):
    """Calculates the combined world-space bounding box for a list of objects."""
    if not objects:
        return None

    min_coords = Vector((float('inf'), float('inf'), float('inf')))
    max_coords = Vector((float('-inf'), float('-inf'), float('-inf')))

    for obj in objects:
        bpy.context.view_layer.update() # Ensure transforms are applied for accurate world bounding box calculation
        if obj.type == 'MESH' or obj.type == 'EMPTY':
            for corner in obj.bound_box:
                world_corner = obj.matrix_world @ Vector(corner)
                min_coords.x = min(min_coords.x, world_corner.x)
                min_coords.y = min(min_coords.y, world_corner.y)
                min_coords.z = min(min_coords.z, world_corner.z)
                max_coords.x = max(max_coords.x, world_corner.x)
                max_coords.y = max(max_coords.y, world_corner.y)
                max_coords.z = max(max_coords.z, world_corner.z)
    
    if min_coords.x == float('inf'):
        return None

    center_x = (min_coords.x + max_coords.x) / 2
    center_y = (min_coords.y + max_coords.y) / 2

    return {
        'min': min_coords,
        'max': max_coords,
        'center_xy': Vector((center_x, center_y, 0)),
        'bottom_center': Vector((center_x, center_y, min_coords.z)),
        'height': max_coords.z - min_coords.z
    }

def get_scaled_width_of_model(source_obj_data, scale_factor):
    """
    Calculates the width of a model if it were scaled.
    Assumes initial rotation and base scaling are already baked into source_obj_data.
    """
    temp_obj = bpy.data.objects.new("TempModelDimCalc", source_obj_data)
    bpy.context.collection.objects.link(temp_obj)
    temp_obj.scale = (scale_factor, scale_factor, scale_factor)
    bpy.context.view_layer.update()
    width, _, _ = get_bounding_box_dimensions(temp_obj)
    bpy.data.objects.remove(temp_obj, do_unlink=True)
    return width

def setup_materials():
    """Creates or reuses a generic model material."""
    if "Model_Material" in bpy.data.materials:
        mat = bpy.data.materials["Model_Material"]
        mat.node_tree.nodes["Principled BSDF"].inputs['Base Color'].default_value = MODEL_COLOR
    else:
        mat = bpy.data.materials.new(name="Model_Material")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        nodes.clear()
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.inputs['Base Color'].default_value = MODEL_COLOR
        output = nodes.new('ShaderNodeOutputMaterial')
        mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    return {"model": mat}

def _process_models_batch():
    """
    Processes a batch of models. Uses a global _batch_context dictionary
    to access necessary variables.
    """
    context = _batch_context

    model_data_to_process = context['model_data_to_process']
    source_model_obj = context['source_model_obj']
    materials = context['materials']
    duplicates_collection = context['duplicates_collection']
    data_column_name_for_batch = context['data_column_name_for_batch']

    # Update batch indices *before* processing this batch
    batch_start = context['current_model_index']
    batch_end = min(context['current_model_index'] + BATCH_SIZE, len(model_data_to_process))
    context['current_model_index'] = batch_end # Update for the next batch

    if not source_model_obj or not source_model_obj.data:
        print("Error: Source model or its data is missing. Cannot process batch.")
        bpy.app.timers.unregister(_process_models_batch)
        _batch_context['cleanup_func'](context['root_collection_name'])
        return

    for i in range(batch_start, batch_end):
        model_data = model_data_to_process[i]
        category = model_data['Category']
        data_value = model_data['DataValue']
        scale_factor = model_data['scale_factor']
        current_model_width = model_data['width']

        # Determine the X position for the *current* model
        # The origin of the model is at its bottom-center after normalization.
        # So, to place its left edge at 'current_x_position_for_next_model',
        # its center needs to be at 'current_x_position_for_next_model + current_model_width / 2'.
        x_position_for_current_model = context['current_x_position_for_next_model'] + (current_model_width / 2)

        duplicated_obj = source_model_obj.copy()
        duplicated_obj.data = source_model_obj.data.copy()
        duplicated_obj.name = f"VizModel_{category}"
        duplicates_collection.objects.link(duplicated_obj)

        if materials["model"]:
            if len(duplicated_obj.data.materials) == 0:
                duplicated_obj.data.materials.append(materials["model"])
            else:
                duplicated_obj.data.materials[0] = materials["model"]

        duplicated_obj.scale = (scale_factor, scale_factor, scale_factor)
        bpy.context.view_layer.objects.active = duplicated_obj
        duplicated_obj.select_set(True)
        # Apply only the new data-driven scale here. Location and initial rotation/scale are baked.
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        duplicated_obj.select_set(False)

        # Since the source model's origin is now at its bottom-center and its initial transforms are baked,
        # setting duplicated_obj.location.z to 0 will place its base on the ground.
        # Use the newly calculated x_position_for_current_model.
        duplicated_obj.location = (x_position_for_current_model, 0, 0)

        # Custom properties
        duplicated_obj["Category"] = category
        duplicated_obj["Population"] = model_data['Population']
        duplicated_obj[data_column_name_for_batch] = data_value

        proportional_gap_part = 0.0
        if i < len(model_data_to_process) - 1:
            next_model_width = model_data_to_process[i+1]['width']
            proportional_gap_part = (current_model_width / 2 + next_model_width / 2) * PROPORTIONAL_GAP_FACTOR

        total_gap = max(MIN_CLEARANCE_BETWEEN_MODELS, proportional_gap_part)
        
        # Update the starting X position for the *next* model
        context['current_x_position_for_next_model'] += current_model_width + total_gap

        print(f"Placed {duplicated_obj.name} (Scale: {scale_factor:.2f}, Width: {current_model_width:.2f}) at X={duplicated_obj.location.x:.2f}")

    if context['current_model_index'] < len(model_data_to_process):
        bpy.app.timers.register(_process_models_batch, first_interval=BATCH_DELAY_SECONDS)
    else:
        print("Script finished successfully!")
        _batch_context.clear()


# --- Main Script Execution Function ---

def run_visualization(
    model_path: str,
    csv_file_path: str,
    visualization_name: str = "MyVisualization",
    data_column_name: str = DEFAULT_DATA_COLUMN_NAME,
    category_column_name: str = DEFAULT_CATEGORY_COLUMN_NAME,
    population_column_name: str = DEFAULT_POPULATION_COLUMN_NAME,
    initial_model_rotation: tuple = (0, 0, 0)
):
    """
    Runs the visualization process with the specified model and data columns.
    """
    global _batch_context

    model_file_name = os.path.splitext(os.path.basename(model_path))[0]
    root_collection_name = f"{visualization_name}_{model_file_name}"
    source_collection_name = f"Source_{model_file_name}_Model"
    duplicates_collection_name = f"Viz_{model_file_name}_Duplicates"

    _batch_context.clear()

    # --- 1. Setup Collections ---
    master_collection = bpy.context.scene.collection
    
    root_collection = get_or_create_collection(master_collection, root_collection_name)
    source_collection = get_or_create_collection(root_collection, source_collection_name)
    source_collection.hide_viewport = True
    source_collection.hide_render = True
    duplicates_collection = get_or_create_collection(root_collection, duplicates_collection_name)

    print(f"Visualization Root: '{root_collection_name}'. Sub-collections created/found.")

    # --- 2. Import the GLTF Model ONCE and Normalize it ---
    source_model_obj = None
    temp_import_collection = None # Initialize for cleanup in case of early error
    try:
        existing_source_objs = [obj for obj in source_collection.objects if obj.type == 'MESH' and obj.name.startswith("VizModel_Source")]
        if existing_source_objs:
            source_model_obj = existing_source_objs[0]
            print(f"Reusing existing source model: '{source_model_obj.name}' from '{source_collection.name}'.")
        else:
            bpy.ops.import_scene.gltf(filepath=model_path)
            imported_objects = [obj for obj in bpy.context.selected_objects]
            bpy.ops.object.select_all(action='DESELECT')

            if not imported_objects:
                print(f"Error: No objects were imported or selected after GLTF import from '{model_path}'.")
                return

            # --- Start: Robust Global Centering of the Entire Imported Scene ---
            temp_import_collection = bpy.data.collections.new("TEMP_Import_Collection_For_Centering")
            bpy.context.scene.collection.children.link(temp_import_collection)

            all_imported_scene_objects = []
            for obj in imported_objects:
                # Unlink from any default collections (like Scene Collection)
                for coll in obj.users_collection:
                    if coll != temp_import_collection:
                        coll.objects.unlink(obj)
                temp_import_collection.objects.link(obj) # Link to temp collection
                all_imported_scene_objects.append(obj)

            # Calculate combined bounding box of all objects imported from the GLTF scene
            combined_bounds = get_combined_bounding_box_world(all_imported_scene_objects)

            if combined_bounds:
                # Calculate the translation needed to move bottom-center to (0,0,0)
                translation_vector = Vector((
                    -combined_bounds['bottom_center'].x,
                    -combined_bounds['bottom_center'].y,
                    -combined_bounds['bottom_center'].z
                ))
                
                # Apply this translation to each object's world location
                for obj in all_imported_scene_objects:
                    obj.location += translation_vector
                print(f"Imported scene (all objects) globally centered and base at Z=0. Offset applied: {translation_vector.x:.2f}, {translation_vector.y:.2f}, {translation_vector.z:.2f}")
            else:
                print("Warning: Could not calculate combined bounding box for imported objects. Scene might not be properly centered.")

            # --- End: Robust Global Centering ---

            # Find the primary mesh object to use as the source model
            # This is done AFTER global centering, so objects have their correct world locations
            for obj in all_imported_scene_objects:
                if obj.type == 'MESH':
                    source_model_obj = obj
                    break
                elif obj.type == 'EMPTY' and obj.children:
                    for child in obj.children_recursive:
                        if child.type == 'MESH':
                            source_model_obj = child
                            break
                if source_model_obj:
                    break

            if not source_model_obj:
                print("Error: Could not find a mesh object in the imported GLTF model or its hierarchy to use as the primary source model.")
                for obj in list(temp_import_collection.objects):
                    temp_import_collection.objects.unlink(obj)
                    bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(temp_import_collection)
                return

            # --- Set Source Model Origin to its Bottom Center (locally) and apply initial transforms ---
            bpy.context.view_layer.objects.active = source_model_obj
            source_model_obj.select_set(True)
            bpy.context.view_layer.update()

            # Apply the desired initial rotation first
            source_model_obj.rotation_euler = initial_model_rotation
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False) # Bake rotation

            # Calculate world position of the source model's bottom-center for setting cursor
            bbox_corners_world = [source_model_obj.matrix_world @ Vector(corner) for corner in source_model_obj.bound_box]
            world_min_z = min(v.z for v in bbox_corners_world)
            world_center_x = (min(v.x for v in bbox_corners_world) + max(v.x for v in bbox_corners_world)) / 2
            world_center_y = (min(v.y for v in bbox_corners_world) + max(v.y for v in bbox_corners_world)) / 2
            
            # Set 3D cursor to this world bottom-center position
            bpy.context.scene.cursor.location = Vector((world_center_x, world_center_y, world_min_z))
            
            # Set the source_model_obj's origin to the 3D cursor's location
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
            
            # Now, move the source_model_obj itself so its newly set origin is at (0,0,0) world space.
            # This places its bottom-center at (0,0,0).
            source_model_obj.location = (0,0,0)
            print("Source model's origin set to its bottom-center, and object moved to (0,0,0).")

            # --- Apply initial uniform scaling to match TARGET_BASE_DIMENSION ---
            bpy.context.view_layer.update() # Update dimensions after origin set and location move
            current_width, current_depth, _ = get_bounding_box_dimensions(source_model_obj)
            
            largest_horizontal_dim = max(current_width, current_depth)
            
            if largest_horizontal_dim > 1e-6: # Avoid division by zero or very small numbers
                base_scale_factor = TARGET_BASE_DIMENSION / largest_horizontal_dim
                source_model_obj.scale *= base_scale_factor
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True) # Bake this initial scale
                print(f"Source model scaled to target base dimension ({TARGET_BASE_DIMENSION:.2f}). Scale factor applied: {base_scale_factor:.4f}")

            # Final check on dimensions after all initial adjustments
            final_initial_width, final_initial_depth, final_initial_height = get_bounding_box_dimensions(source_model_obj)
            print(f"Source model final initial dimensions (W,D,H): {final_initial_width:.2f}, {final_initial_depth:.2f}, {final_initial_height:.2f}")

            source_model_obj.select_set(False)

            # Move all objects from the temporary import collection to the final source collection
            for obj in list(temp_import_collection.objects):
                temp_import_collection.objects.unlink(obj)
                source_collection.objects.link(obj)
            bpy.data.collections.remove(temp_import_collection)

            print(f"Source model '{source_model_obj.name}' and related imported scene elements moved to '{source_collection.name}' and hidden, normalized.")

    except Exception as e:
        print(f"Error importing or normalizing GLTF model: {e}")
        import traceback
        traceback.print_exc()
        clear_script_generated_elements(root_collection_name)
        if temp_import_collection and temp_import_collection.name in bpy.data.collections:
            for obj in list(temp_import_collection.objects):
                temp_import_collection.objects.unlink(obj)
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections.remove(temp_import_collection)
        _batch_context.clear()
        return

    # --- Setup Materials ---
    materials = setup_materials()

    # --- 3. Parse CSV Data ---
    world_data = parse_csv_data(csv_file_path, data_column_name, category_column_name, population_column_name)
    if not world_data:
        print("No valid data parsed from CSV. Exiting.")
        clear_script_generated_elements(root_collection_name)
        _batch_context.clear()
        return

    data_values = [d['DataValue'] for d in world_data]
    min_data = min(data_values)
    max_data = max(data_values)
    print(f"Min '{data_column_name}': {min_data}, Max '{data_column_name}': {max_data}")

    # --- 4. Pre-calculate Scaled Dimensions for all Models ---
    model_data_to_process = []
    source_mesh_data = source_model_obj.data

    for i, row in enumerate(world_data):
        data_value = row['DataValue']
        scale_factor = MIN_VISUAL_SCALE
        if max_data > min_data:
            if USE_LINEAR_SCALING:
                normalized_value = (data_value - min_data) / (max_data - min_data)
                normalized_value_powered = normalized_value ** SCALING_POWER
                scale_factor = MIN_VISUAL_SCALE + (normalized_value_powered * (MAX_VISUAL_SCALE - MIN_VISUAL_SCALE))
            else:
                log_min_value = math.log(min_data + 1e-9)
                log_max_value = math.log(max_data + 1e-9)
                log_value = math.log(data_value + 1e-9)
                
                log_range = log_max_value - log_min_value
                if log_range > 1e-9:
                    normalized_log_value = (log_value - log_min_value) / log_range
                    normalized_log_value_powered = normalized_log_value ** SCALING_POWER
                    scale_factor = MIN_VISUAL_SCALE + (normalized_log_value_powered * (MAX_VISUAL_SCALE - MIN_VISUAL_SCALE))
                else:
                    scale_factor = MIN_VISUAL_SCALE

        calculated_width = get_scaled_width_of_model(source_mesh_data, scale_factor)
        model_data_to_process.append({
            'Category': row['Category'],
            'DataValue': data_value,
            'Population': row['Population'],
            'scale_factor': scale_factor,
            'width': calculated_width
        })

    print(f"Pre-calculated widths for {len(model_data_to_process)} models. Starting batched placement...")

    # --- 5. Prepare and Start Batched Creation and Placement of Models ---
    _batch_context['model_data_to_process'] = model_data_to_process
    _batch_context['source_model_obj'] = source_model_obj
    _batch_context['materials'] = materials
    _batch_context['duplicates_collection'] = duplicates_collection
    _batch_context['data_column_name_for_batch'] = data_column_name
    _batch_context['root_collection_name'] = root_collection_name
    _batch_context['cleanup_func'] = clear_script_generated_elements

    _batch_context['current_model_index'] = 0
    _batch_context['current_x_position_for_next_model'] = 0.0 # This now represents the left edge for the next model

    bpy.app.timers.register(_process_models_batch, first_interval=BATCH_DELAY_SECONDS)


# --- How to Run the Visualization (Deploy) ---
if __name__ == "__main__":
    # Ensure you have Blender running and this script is executed within Blender's text editor.
    # Update the model_path and csv_file_path to your actual file locations.

    # --- Example 1: Pyramids (using GDP) ---
    print("\n--- Running with Pyramid Model (GDP) ---")
    run_visualization(
        model_path=r"C:\Users\User\Downloads\sphere.glb", # <--- UPDATE THIS PATH
        csv_file_path=r"C:\Data\WorldStats.csv", # Provide the CSV file path here
        visualization_name="CountryGDP_Viz",
        data_column_name="GDP",
        category_column_name="Country",
        initial_model_rotation=(math.radians(90), 0, 0) # Specific orientation (e.g., if model is imported lying down)
    )


    # --- Example 3: Obese People (using a hypothetical 'Obesity_Rate' column) ---
    # Uncomment this example to run it. Make sure to update the model_path.
    # print("\n--- Running with Obese Person Model (Obesity Rate) ---")
    # run_visualization(
    #    model_path=r"G:\Models\obese_person\scene.gltf", # <--- UPDATE THIS PATH
    #    csv_file_path=r"C:\Data\WorldStats.csv",
    #    visualization_name="HealthData_BMI",
    #    data_column_name="Obesity_Rate",
    #    category_column_name="Country",
    #    population_column_name="Population",
    #    initial_model_rotation=(0, 0, 0)
    # )