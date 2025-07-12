import bpy
import os
import sys
import importlib
import traceback
import math

# --- VERY EARLY DEBUG PRINT ---
print("--- Init_Blender_Animation.py: Script started execution ---")

# --- USER-DEFINED SCRIPT DIRECTORY ---
# Set this to the ABSOLUTE PATH of the directory where ALL your Python scripts
# (Init_Blender_Animation.py, Stats_Generator.py, Blender_Graph_Animator.py,
# and Blender_Camera_Animator.py) are located.
#
# IMPORTANT: All scripts MUST be in this exact directory for imports to work.
# If you move this directory, you MUST update this path manually.
script_dir = r"G:\Scripts\Blender\blender_data_viz_pipeline"  # <--- YOUR HARDCODED SCRIPT FOLDER PATH

print(f"DEBUG: Using manually specified script directory: {script_dir}")

# Add the directory of this script to the Python path
# This ensures Blender can find the other scripts when imported.
if script_dir and script_dir not in sys.path:
    sys.path.append(script_dir)
    print(f"Added script directory to Python path: {script_dir}")
elif script_dir:
    print(f"Script directory already in Python path: {script_dir}")
else:
    print("ERROR: Script directory not set. Path resolution failed.")

# Flags to track successful imports
stats_generator_imported = False
blender_graph_animator_imported = False
blender_camera_animator_imported = False

# Attempt to import the other scripts
try:
    import Stats_Generator
    stats_generator_imported = True
    import Blender_Graph_Animator
    blender_graph_animator_imported = True
    import Blender_Camera_Animator
    blender_camera_animator_imported = True
    print("Successfully imported Stats_Generator, Blender_Graph_Animator, Blender_Camera_Animator.")
except ImportError as e:
    print(f"Error importing required scripts: {e}")
    print(
        "Please ensure 'Stats_Generator.py', 'Blender_Graph_Animator.py', and 'Blender_Camera_Animator.py' are in the directory specified in 'script_dir'.")
    # Do NOT sys.exit() here, as it might prevent the console from showing the error
    # Let the script continue to register the operator if possible, but it will likely fail later.
except Exception as e:
    print(f"An unexpected error occurred during module import: {e}")
    traceback.print_exc()

# Reload modules only if they were successfully imported
if stats_generator_imported:
    try:
        importlib.reload(Stats_Generator)
        print("Reloaded Stats_Generator.")
    except Exception as e:
        print(f"Error reloading Stats_Generator: {e}")
        traceback.print_exc()
if blender_graph_animator_imported:
    try:
        importlib.reload(Blender_Graph_Animator)
        print("Reloaded Blender_Graph_Animator.")
    except Exception as e:
        print(f"Error reloading Blender_Graph_Animator: {e}")
        traceback.print_exc()
if blender_camera_animator_imported:
    try:
        importlib.reload(Blender_Camera_Animator)
        print("Reloaded Blender_Camera_Animator.")
    except Exception as e:
        print(f"Error reloading Blender_Camera_Animator: {e}")
        traceback.print_exc()

# --- GLOBAL USER CONFIGURATION ---
# All user-configurable parameters are defined here.

GLOBAL_SCENE_CONFIG = {
    "REBUILD_ALL_ON_RUN": True,  # Set to True to clear all script-generated elements and rebuild from scratch
    "SAVE_BLENDER_FILE_AFTER_RUN": False,
    "BLENDER_SAVE_PATH": r"C:\BlenderProjects\MyDataVizAnimation.blend"
}

STATS_GENERATOR_CONFIG = {
    "MODEL_PATH": r"C:\Users\User\Downloads\sphere.glb",  # <--- UPDATE THIS PATH to your 3D model
    "CSV_FILE_PATH": r"C:\Data\WorldStats.csv",  # <--- UPDATE THIS PATH to your CSV data
    "VISUALIZATION_NAME": "CountryGDP_Viz",
    "DATA_COLUMN_NAME": "GDP",
    "CATEGORY_COLUMN_NAME": "Country",
    "POPULATION_COLUMN_NAME": "Population",  # Set to a valid column name if available, otherwise 'Population'
    "INITIAL_MODEL_ROTATION": (math.radians(90), 0, 0),
    # Example: (math.radians(90), 0, 0) if model is imported lying down
    "USE_LINEAR_SCALING": True,
    "MIN_VISUAL_SCALE": 5.0,
    "MAX_VISUAL_SCALE": 300.0,
    "SCALING_POWER": 1.5,
    "PROPORTIONAL_GAP_FACTOR": 0.5,
    "MIN_CLEARANCE_BETWEEN_MODELS": 2.0,
    "MODEL_COLOR": (0.8, 0.2, 0.1, 1.0),  # RGBA (Reddish)
    "TARGET_BASE_DIMENSION": 1.0,  # Ensures source model has a consistent horizontal footprint
    "BATCH_SIZE": 10,  # Number of models to process per batch (for efficiency)
    "BATCH_DELAY_SECONDS": 0.01  # Delay between batches
}

GRAPH_ANIMATOR_CONFIG = {
    # GRAPH_CSV_FILE_PATH, GRAPH_DATA_COLUMN, GRAPH_MONTH_COLUMN are now only for fallback if stats_generator data is not used
    "GRAPH_CSV_FILE_PATH": r"C:\Data\Database.csv",
    # <--- This path is now only used if Stats_Generator data is unavailable
    "GRAPH_DATA_COLUMN": "Sales",  # <--- This column name is now only used if Stats_Generator data is unavailable
    "GRAPH_MONTH_COLUMN": "Month",  # <--- This column name is now only used if Stats_Generator data is unavailable
    "DATA_UNIT_SYMBOL": "",  # Set this to your desired unit symbol (e.g., "$", "K", "ppm", "%")
    "GRAPH_ANIM_START_FRAME": 2,
    "GRAPH_ANIM_LENGTH_DATA": 100,  # Frames per data point for animation
    "GRAPH_START_POSITION": 0,  # This will be largely overridden by stats_model_positions
    "GRAPH_X_AXIS_SPREAD": 2,  # This will be largely overridden by stats_model_positions
    "ANIMATED_OBJECT_TYPE": "CYLINDER",  # 'CUBE', 'CONE', or 'CYLINDER'
    "ANIMATED_OBJECT_NAME": "Animated_Graph_Object",
    "ANIMATED_OBJECT_SCALE": 0.1,
    "REBUILD_GRAPH_ON_RUN": False,  # Graph animator also has its own rebuild flag
}

CAMERA_ANIMATOR_CONFIG = {
    "CAMERA_MODE": 'SIDEWAYS_TRACKING_VIEW',  # 'SIDEWAYS_TRACKING_VIEW' or 'OVERHEAD_TRACKING_VIEW'
    "MIN_CAMERA_CLEARANCE": 2.0,  # Minimum distance camera must maintain from any object
    "DYNAMIC_MOVEMENT_INTENSITY": 1.0,  # Multiplier for overall camera's dynamic shifts
    # --- NEW DYNAMIC CAMERA SETTINGS ---
    "CAMERA_DYNAMIC_ZOOM_FACTOR": 5.0,  # Max +/- change in focal length for dynamic zoom
    "CAMERA_VERTICAL_BOB_AMPLITUDE": 1.0,  # Max +/- change in vertical position for bobbing
    "CAMERA_HORIZONTAL_DRIFT_AMPLITUDE": 2.0, # Max +/- change in horizontal position for drifting
    "CAMERA_DYNAMIC_MOTION_FREQUENCY": 20.0, # Frames per oscillation cycle (e.g., 20.0 for 1 cycle every 20 frames)
    # --- NEW BASE CAMERA OFFSETS ---
    "CAMERA_BASE_VERTICAL_OFFSET_FACTOR": 0.2, # Multiplier for max_dim to set base camera Z-offset (smaller = lower)
    "CAMERA_BASE_HORIZONTAL_OFFSET_FACTOR": 1.5 # Multiplier for min_camera_clearance to set sideways X-offset (larger = further)
}


# --- END GLOBAL USER CONFIGURATION ---


def print_status(message):
    """Helper function to print status messages."""
    print(f"\n--- {message} ---")


def clear_all_script_generated_elements():
    """
    Clears all collections and objects created by these scripts.
    This is a more aggressive cleanup for a full rebuild.
    """
    print_status("Initiating full scene cleanup for rebuild...")

    collections_to_remove = [
        col for col in bpy.data.collections
        if col.name.startswith("Viz_") or
           col.name.startswith("Source_") or
           col.name.startswith("CountryGDP_Viz_") or  # Specific to Stats_Generator default
           col.name == "Graph_Elements" or
           col.name == "Camera_Animations" or
           col.name == "TEMP_Import_Collection_For_Centering"  # From Stats_Generator temp
    ]

    # Deselect all objects first
    bpy.ops.object.select_all(action='DESELECT')

    # Delete objects linked to these collections
    for collection in collections_to_remove:
        print(f"Cleaning collection: {collection.name}")
        for obj in list(collection.objects):  # Iterate over a copy of the list
            # Preserve the default scene camera if it's not our main viz camera
            if obj.name == "Camera" and obj.name != "Main_Visualization_Camera":
                continue

                # Unlink from all collections it's part of
            for coll in list(obj.users_collection):
                coll.objects.unlink(obj)
            # Remove if no other collections are using it
            if not obj.users_collection:
                bpy.data.objects.remove(obj, do_unlink=True)
            else:
                print(f"Object '{obj.name}' still linked to other collections, not deleting.")

    # Delete the collections themselves, in reverse order of creation (children first)
    for collection in reversed(collections_to_remove):
        if collection.name in bpy.data.collections:
            # Ensure it's empty before removal
            if not collection.objects and not collection.children:
                bpy.data.collections.remove(collection)
                print(f"Removed collection: {collection.name}")
            else:
                print(f"Collection '{collection.name}' not empty, skipping removal.")

    # Clean up any remaining materials created by the scripts
    mats_to_remove = []
    for mat in bpy.data.materials:
        if mat.name.startswith("Model_Material") or mat.name.startswith("graph_material_"):
            is_used = False
            for mesh in bpy.data.meshes:
                if mat in mesh.materials:
                    is_used = True
                    break
            if not is_used:
                mats_to_remove.append(mat)
    for mat in mats_to_remove:
        bpy.data.materials.remove(mat)
        print(f"Removed unused material: {mat.name}")

    # Clean up any remaining curves
    curves_to_remove = []
    for curve in bpy.data.curves:
        if curve.name.startswith("data_curve") or curve.name.startswith("Dynamic_Camera_Path"):
            if not curve.users:  # Check if it has no users (objects using this curve data)
                curves_to_remove.append(curve)
    for curve in curves_to_remove:
        bpy.data.curves.remove(curve)
        print(f"Removed unused curve data: {curve.name}")

    print_status("Full scene cleanup complete.")


# Global variable to store results from Stats_Generator for the callback
_stats_generator_results = None


def stats_generator_completion_callback(model_collection_name, all_model_data_list):
    """
    Callback function executed by Stats_Generator after all models are placed.
    This function then triggers the graph and camera animation.
    """
    global _stats_generator_results
    _stats_generator_results = {
        "model_collection_name": model_collection_name,
        "all_model_data": all_model_data_list  # This now includes DataValue, Category, world_x_pos, world_top_z
    }
    print_status("Stats_Generator finished. Proceeding to Graph and Camera Animation.")

    # Schedule the next step to run after this callback completes
    bpy.app.timers.register(_run_graph_and_camera_animation_step, first_interval=0.1)


def _run_graph_and_camera_animation_step():
    """
    Internal function to run graph and camera animation,
    called by the timer after Stats_Generator completes.
    """
    global _stats_generator_results
    if not _stats_generator_results:
        print("Error: Stats_Generator results not available. Cannot proceed.")
        return

    model_collection_name = _stats_generator_results["model_collection_name"]
    all_model_data = _stats_generator_results["all_model_data"]  # This contains the x_pos and top_z for each model

    # --- Extract data for the graph directly from Stats_Generator's output ---
    graph_data_values = [d['DataValue'] for d in all_model_data]
    graph_category_labels = [d['Category'] for d in all_model_data]

    # Also prepare the graph_point_positions for Blender_Graph_Animator
    # This ensures the graph points align perfectly with the stats models
    graph_point_positions_for_graph = [
        {'x_pos': d['world_x_pos'], 'base_z': d['world_top_z']}
        for d in all_model_data
    ]

    # Determine animation end frame based on data length
    graph_number_of_data = len(graph_data_values)
    if graph_number_of_data == 0:
        print(
            "Warning: No valid data for graph generation from Stats_Generator output. Graph animation will be skipped.")
        graph_anim_end_frame = STATS_GENERATOR_CONFIG["BATCH_SIZE"] * 10  # Fallback
    else:
        graph_anim_end_frame = GRAPH_ANIMATOR_CONFIG["GRAPH_ANIM_START_FRAME"] + \
                               GRAPH_ANIMATOR_CONFIG["GRAPH_ANIM_LENGTH_DATA"] * (graph_number_of_data - 1)

    # --- Step 2: Generate Graph Animation ---
    print_status("Generating Graph Animation...")
    graph_results = Blender_Graph_Animator.generate_graph_animation(
        graph_data_values=graph_data_values,  # Pass extracted data values
        graph_category_labels=graph_category_labels,  # Pass extracted category labels
        data_unit_symbol=GRAPH_ANIMATOR_CONFIG["DATA_UNIT_SYMBOL"],
        graph_anim_start_frame=GRAPH_ANIMATOR_CONFIG["GRAPH_ANIM_START_FRAME"],
        graph_anim_length_data=GRAPH_ANIMATOR_CONFIG["GRAPH_ANIM_LENGTH_DATA"],
        graph_start_position=GRAPH_ANIMATOR_CONFIG["GRAPH_START_POSITION"],  # These are now mostly ignored
        graph_x_axis_spread=GRAPH_ANIMATOR_CONFIG["GRAPH_X_AXIS_SPREAD"],  # These are now mostly ignored
        animated_object_type=GRAPH_ANIMATOR_CONFIG["ANIMATED_OBJECT_TYPE"],
        animated_object_name=GRAPH_ANIMATOR_CONFIG["ANIMATED_OBJECT_NAME"],
        animated_object_scale=GRAPH_ANIMATOR_CONFIG["ANIMATED_OBJECT_SCALE"],
        rebuild_graph_on_run=GRAPH_ANIMATOR_CONFIG["REBUILD_GRAPH_ON_RUN"],
        graph_point_positions=graph_point_positions_for_graph  # Pass the precise positions
    )

    if not graph_results:
        print("Error: Graph animation generation failed. Camera animation might be affected.")
        # Set dummy values if graph generation failed, to allow camera to proceed
        graph_curve_object_name = None
        graph_animated_object_name = None
    else:
        graph_curve_object_name = graph_results["curve_object_name"]
        graph_animated_object_name = graph_results["animated_object_name"]
        # Update global scene end frame based on graph animation if it's longer
        if graph_results["animation_end_frame"] > bpy.context.scene.frame_end:
            bpy.context.scene.frame_end = graph_results["animation_end_frame"] + 50

    # --- Step 3: Generate Camera Animation ---
    print_status("Generating Camera Animation...")
    camera_success = Blender_Camera_Animator.generate_camera_animation(
        camera_mode=CAMERA_ANIMATOR_CONFIG["CAMERA_MODE"],
        model_collection_name=model_collection_name,
        graph_curve_object_name=graph_curve_object_name,
        graph_animated_object_name=graph_animated_object_name,
        animation_start_frame=GRAPH_ANIMATOR_CONFIG["GRAPH_ANIM_START_FRAME"],
        animation_end_frame=bpy.context.scene.frame_end,
        min_camera_clearance=CAMERA_ANIMATOR_CONFIG["MIN_CAMERA_CLEARANCE"],
        dynamic_movement_intensity=CAMERA_ANIMATOR_CONFIG["DYNAMIC_MOVEMENT_INTENSITY"],
        # --- NEW PARAMETERS PASSED ---
        camera_dynamic_zoom_factor=CAMERA_ANIMATOR_CONFIG["CAMERA_DYNAMIC_ZOOM_FACTOR"],
        camera_vertical_bob_amplitude=CAMERA_ANIMATOR_CONFIG["CAMERA_VERTICAL_BOB_AMPLITUDE"],
        camera_horizontal_drift_amplitude=CAMERA_ANIMATOR_CONFIG["CAMERA_HORIZONTAL_DRIFT_AMPLITUDE"],
        camera_dynamic_motion_frequency=CAMERA_ANIMATOR_CONFIG["CAMERA_DYNAMIC_MOTION_FREQUENCY"],
        # --- NEW BASE OFFSETS PASSED ---
        camera_base_vertical_offset_factor=CAMERA_ANIMATOR_CONFIG["CAMERA_BASE_VERTICAL_OFFSET_FACTOR"],
        camera_base_horizontal_offset_factor=CAMERA_ANIMATOR_CONFIG["CAMERA_BASE_HORIZONTAL_OFFSET_FACTOR"]
    )

    if camera_success:
        print_status("Camera Animation generated successfully!")
    else:
        print("Error: Camera animation generation failed.")

    # --- Final Steps ---
    if GLOBAL_SCENE_CONFIG["SAVE_BLENDER_FILE_AFTER_RUN"]:
        try:
            bpy.ops.wm.save_as_mainfile(filepath=GLOBAL_SCENE_CONFIG['BLENDER_SAVE_PATH'])
            print(f"Blender file saved to: {GLOBAL_SCENE_CONFIG['BLENDER_SAVE_PATH']}")
        except Exception as e:
            print(f"Error saving Blender file: {e}")
            traceback.print_exc()

    print("\n" + "=" * 50)
    print("FULL ANIMATION PIPELINE COMPLETE!")
    print("=" * 50)


class InitAnimationOperator(bpy.types.Operator):
    """Blender Operator to initialize and run the full animation pipeline."""
    bl_idname = "object.init_animation_pipeline"
    bl_label = "Run Full Animation Pipeline"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            # Check if all modules were successfully imported before proceeding
            if not (stats_generator_imported and blender_graph_animator_imported and blender_camera_animator_imported):
                self.report({'ERROR'}, "Required scripts did not import successfully. Check console for details.")
                return {'CANCELLED'}

            if GLOBAL_SCENE_CONFIG["REBUILD_ALL_ON_RUN"]:
                clear_all_script_generated_elements()

            print_status("Starting Stats Model Generation...")
            # Stats_Generator will call stats_generator_completion_callback when done
            Stats_Generator.generate_stats_models(
                model_path=STATS_GENERATOR_CONFIG["MODEL_PATH"],
                csv_file_path=STATS_GENERATOR_CONFIG["CSV_FILE_PATH"],
                visualization_name=STATS_GENERATOR_CONFIG["VISUALIZATION_NAME"],
                data_column_name=STATS_GENERATOR_CONFIG["DATA_COLUMN_NAME"],
                category_column_name=STATS_GENERATOR_CONFIG["CATEGORY_COLUMN_NAME"],
                population_column_name=STATS_GENERATOR_CONFIG["POPULATION_COLUMN_NAME"],
                initial_model_rotation=STATS_GENERATOR_CONFIG["INITIAL_MODEL_ROTATION"],
                use_linear_scaling=STATS_GENERATOR_CONFIG["USE_LINEAR_SCALING"],
                min_visual_scale=STATS_GENERATOR_CONFIG["MIN_VISUAL_SCALE"],
                max_visual_scale=STATS_GENERATOR_CONFIG["MAX_VISUAL_SCALE"],
                scaling_power=STATS_GENERATOR_CONFIG["SCALING_POWER"],
                proportional_gap_factor=STATS_GENERATOR_CONFIG["PROPORTIONAL_GAP_FACTOR"],
                min_clearance_between_models=STATS_GENERATOR_CONFIG["MIN_CLEARANCE_BETWEEN_MODELS"],
                model_color=STATS_GENERATOR_CONFIG["MODEL_COLOR"],
                target_base_dimension=STATS_GENERATOR_CONFIG["TARGET_BASE_DIMENSION"],
                batch_size=STATS_GENERATOR_CONFIG["BATCH_SIZE"],
                batch_delay_seconds=STATS_GENERATOR_CONFIG["BATCH_DELAY_SECONDS"],
                rebuild_on_run=GLOBAL_SCENE_CONFIG["REBUILD_ALL_ON_RUN"],  # Pass global rebuild flag
                completion_callback=stats_generator_completion_callback  # Pass the callback
            )

            self.report({'INFO'}, "Animation pipeline initiated. Check console for progress.")
            return {'FINISHED'}
        except Exception as e:
            print(f"An error occurred during pipeline initiation: {e}")
            traceback.print_exc()
            self.report({'ERROR'}, f"Pipeline initiation failed: {e}")
            return {'CANCELLED'}


# Define the panel class explicitly
class VIEW3D_PT_tools_init_animation(bpy.types.Panel):
    bl_label = "Animation Pipeline"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Animation Tools"

    def draw(self, context):
        layout = self.layout
        layout.operator(InitAnimationOperator.bl_idname)


def register():
    # Ensure unregister is called first to prevent re-registration errors
    try:
        unregister()
    except RuntimeError:
        pass  # Ignore if not registered yet or already handled by `main` block

    bpy.utils.register_class(InitAnimationOperator)
    bpy.utils.register_class(VIEW3D_PT_tools_init_animation)  # Register the new class
    print("InitAnimationOperator and Panel registered.")


def unregister():
    # Unregister the operator first
    try:
        bpy.utils.unregister_class(InitAnimationOperator)
        print("InitAnimationOperator unregistered.")
    except RuntimeError:
        pass  # Ignore if not registered

    # Unregister the panel
    try:
        bpy.utils.unregister_class(VIEW3D_PT_tools_init_animation)
        print("Animation Pipeline Panel unregistered.")
    except RuntimeError:
        pass  # Ignore if not registered


if __name__ == "__main__":
    # Ensure all scripts are unregistered and re-registered for fresh runs
    # This block is for direct execution of this script in Blender's text editor
    # It ensures a clean state for development.
    print("--- Running Init_Blender_Animation.py as main ---")

    # Attempt to unregister classes from other modules first
    for module_name in ["Stats_Generator", "Blender_Graph_Animator", "Blender_Camera_Animator"]:
        if module_name in sys.modules:
            module = sys.modules[module_name]
            if hasattr(module, 'unregister') and callable(module.unregister):
                try:
                    module.unregister()
                    print(f"Attempted unregister for {module_name}")
                except Exception:
                    pass  # Ignore if not registered or error during unregister

    # Now, unregister and register classes from *this* module.
    # The unregister() function in this file is designed to handle missing classes gracefully.
    try:
        unregister()
        print("Successfully unregistered Init_Blender_Animation classes (if registered).")
    except Exception as e:
        print(f"Warning: Error during unregister of Init_Blender_Animation classes: {e}")
        traceback.print_exc()
        pass  # Continue even if unregister fails for some reason

    register()
    print("Init_Blender_Animation.py loaded. Use the 'Animation Pipeline' panel in the N-panel (3D Viewport) to run.")