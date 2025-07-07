import bpy
import os
import mathutils
import traceback
import time # For potential future use, e.g., pausing between batches

# --- USER CONFIGURATION ---
MODEL_PATH = r"G:\Models\asian_themed_low_poly_night_city_buildings\scene.gltf"
MODEL_TYPE = 'GLTF'

# Grid dimensions for duplication
DUPLICATION_GRID_X = 5
DUPLICATION_GRID_Y = 3

# Spacing between duplicated models
SPACING_X = 30.0
SPACING_Y = 40.0

# Overall position and scale of the entire background
BACKGROUND_GLOBAL_LOCATION = (0, -50, 0)
BACKGROUND_GLOBAL_SCALE = 1.0

# Animation settings
ANIMATE_BACKGROUND = True
BACKGROUND_ANIMATION_START_FRAME = 1
BACKGROUND_ANIMATION_END_FRAME = 250
BACKGROUND_MOVE_DISTANCE_X = 0.0
BACKGROUND_MOVE_DISTANCE_Y = 50.0
BACKGROUND_MOVE_DISTANCE_Z = 0.0

# Batch processing settings for UI responsiveness
BATCH_SIZE = 5 # Number of grid cells to process per UI update cycle. Adjust based on performance.

# Template export settings
SAVE_TEMPLATE_BLEND = False
TEMPLATE_SAVE_PATH = r"C:\BlenderTemplates\MySkylineBackgroundTemplate.blend"

# --- END USER CONFIGURATION ---


def print_debug_info(message):
    """Helper function to print debug information."""
    print(f"[DEBUG] {message}")


def import_and_prepare_model(filepath, file_type):
    """
    Imports a 3D model, applies its transformations, and returns all newly imported objects.
    """
    if not os.path.exists(filepath):
        print(f"Error: Model file NOT found at specified path: {filepath}")
        return None

    print_debug_info(f"Importing model from: {filepath} (Type: {file_type})")
    
    # Get a snapshot of all object names currently in bpy.data.objects before import.
    object_names_before_import = {obj.name for obj in bpy.data.objects}

    try:
        if file_type.upper() == 'GLTF':
            bpy.ops.import_scene.gltf(filepath=filepath)
        elif file_type.upper() == 'OBJ':
            bpy.ops.import_scene.obj(filepath=filepath)
        elif file_type.upper() == 'FBX':
            bpy.ops.import_scene.fbx(filepath=filepath)
        else:
            print(f"Error: Unsupported model type '{file_type}'.")
            return None

        # Find newly imported objects
        newly_imported_objects = []
        for obj in bpy.data.objects:
            if isinstance(obj.name, str) and obj.name not in object_names_before_import:
                newly_imported_objects.append(obj)

        print_debug_info(f"Found {len(newly_imported_objects)} newly imported objects.")
        
        if not newly_imported_objects:
            print("Error: No objects were imported or identified. Check file path and type.")
            return None

        # Identify the top-level object(s) of the newly imported model.
        top_level_imported_roots = [obj for obj in newly_imported_objects if obj.parent is None]
        
        if top_level_imported_roots:
            print_debug_info("Applying transformations to the imported model's root object(s)...")
            bpy.ops.object.select_all(action='DESELECT')
            
            # Select all objects that are part of the imported hierarchy
            all_model_objects = []
            for root_obj in top_level_imported_roots:
                def get_all_children(obj_node):
                    children_list = [obj_node]
                    for child in obj_node.children:
                        children_list.extend(get_all_children(child))
                    return children_list
                all_model_objects.extend(get_all_children(root_obj))

            for obj in all_model_objects:
                obj.select_set(True)
            
            # Set the active object to one of the roots for the apply operator
            if top_level_imported_roots:
                bpy.context.view_layer.objects.active = top_level_imported_roots[0]

            # Apply all transformations (Location, Rotation, Scale)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            print_debug_info("Transformations applied to imported model.")
            bpy.ops.object.select_all(action='DESELECT') # Deselect all after applying

        # Print object names for debugging AFTER applying transforms
        for obj in newly_imported_objects:
            print_debug_info(f"Prepared object: {obj.name} (type: {obj.type}) - Loc:{obj.location} Rot:{obj.rotation_euler} Scale:{obj.scale}")

        return newly_imported_objects

    except Exception as e:
        print(f"Error during model import and preparation: {e}")
        traceback.print_exc()
        return None


def duplicate_object_with_hierarchy(obj, new_name_prefix, parent_map=None):
    """
    Duplicates an object and all its children recursively, giving them new names.
    This function ensures that all data (mesh, materials, etc.) is copied.
    It returns the new duplicated root object.
    
    Args:
        obj (bpy.types.Object): The original object to duplicate.
        new_name_prefix (str): A prefix to add to the names of duplicated objects.
        parent_map (dict, optional): A dictionary to map original objects to their duplicates
                                     to correctly re-establish parenting. Used internally for recursion.
    Returns:
        bpy.types.Object: The newly created duplicated root object.
    """
    if parent_map is None:
        parent_map = {} # Initialize map for the top-level call

    # Create a copy of the object
    new_obj = obj.copy()
    new_obj.name = f"{new_name_prefix}_{obj.name}"

    # Copy object data (e.g., mesh data, curve data)
    if obj.data:
        new_obj.data = obj.data.copy()
        new_obj.data.name = f"{new_name_prefix}_{obj.data.name}"
    
    # Clear animation data from the duplicate to avoid unintended animations
    new_obj.animation_data_clear()

    # DO NOT LINK TO bpy.context.collection HERE.
    # Linking will be handled by link_object_and_hierarchy_to_collection
    # after the entire hierarchy is duplicated.
    # bpy.context.collection.objects.link(new_obj) # <--- REMOVED THIS LINE

    # Add the mapping from original to duplicate
    parent_map[obj] = new_obj

    # Recursively duplicate children
    for child in obj.children:
        new_child = duplicate_object_with_hierarchy(child, new_name_prefix, parent_map)
        # Set parent for the duplicated child
        new_child.parent = new_obj 
        # Copy the inverse parent matrix to maintain relative transform
        new_child.matrix_parent_inverse = child.matrix_parent_inverse.copy()

    return new_obj


def link_object_and_hierarchy_to_collection(obj, target_collection):
    """
    Links an object and its entire hierarchy to a specified collection,
    unlinking them from any other collections first.
    """
    # Get all objects in the hierarchy (including the root)
    all_hierarchy_objects = []
    def get_all_children_recursive(node):
        all_hierarchy_objects.append(node)
        for child in node.children:
            get_all_children_recursive(child)
    get_all_children_recursive(obj)

    for node_obj in all_hierarchy_objects:
        # Unlink from all collections it's currently in
        for coll in list(node_obj.users_collection):
            coll.objects.unlink(node_obj)
        
        # Link to the target collection if not already there
        if node_obj.name not in target_collection.objects: # Check by name for robustness
            target_collection.objects.link(node_obj)


def animate_background(parent_empty, start_frame, end_frame, move_x, move_y, move_z):
    """
    Animates the parent empty to move the entire background grid.
    """
    if not parent_empty:
        print("Error: Parent empty not provided for background animation.")
        return

    print_debug_info(f"Animating background from frame {start_frame} to {end_frame}")
    
    # Clear any existing animation data on the parent empty
    if parent_empty.animation_data:
        parent_empty.animation_data_clear()

    # Get the initial location of the parent empty
    initial_loc = parent_empty.location.copy()

    # Set the first keyframe at the initial location
    parent_empty.location = initial_loc
    parent_empty.keyframe_insert(data_path="location", frame=start_frame)

    # Calculate the end location by adding the movement distances
    end_loc = initial_loc + mathutils.Vector((move_x, move_y, move_z))
    
    # Set the second keyframe at the calculated end location
    parent_empty.location = end_loc
    parent_empty.keyframe_insert(data_path="location", frame=end_frame)

    # Set interpolation to 'LINEAR' for a constant speed movement
    if parent_empty.animation_data and parent_empty.animation_data.action:
        for fcurve in parent_empty.animation_data.action.fcurves:
            if fcurve.data_path.startswith('location'): # Apply to X, Y, Z location F-curves
                for kf in fcurve.keyframe_points:
                    kf.interpolation = 'LINEAR'

    print_debug_info("Background animation setup complete.")


class BackgroundGridGeneratorOperator(bpy.types.Operator):
    """Blender Operator to generate a background grid of duplicated models in batches."""
    bl_idname = "object.background_grid_generator"
    bl_label = "Generate Background Grid (Batch)"
    bl_options = {'REGISTER', 'UNDO'}

    # Operator properties to store state between modal calls
    _timer = None
    _current_i = 0
    _current_j = 0
    _total_cells = 0
    _grid_parent = None
    _grid_collection = None
    _top_level_model_roots = None
    _original_source_objects = None # Store original imported objects for deletion
    _start_x = 0.0
    _start_y = 0.0
    _spacing_x = 0.0
    _spacing_y = 0.0
    _grid_x = 0
    _grid_y = 0

    def execute(self, context):
        # Initial setup when the operator starts
        print_debug_info("Operator execute: Initializing grid generation.")
        
        # Clear selection at the start to avoid unintended operations on existing objects
        bpy.ops.object.select_all(action='DESELECT')

        # 1. Import the model and get references to the newly imported objects
        print_debug_info("Operator execute: Step 1: Importing and preparing model...")
        source_objects = import_and_prepare_model(MODEL_PATH, MODEL_TYPE)
        
        if not source_objects:
            self.report({'ERROR'}, "Failed to import model or no suitable objects found.")
            return {'CANCELLED'}
        
        print_debug_info(f"Model import successful. Found {len(source_objects)} objects that comprise the original model.")

        # Store necessary data in the operator's self for modal function
        self._original_source_objects = source_objects # Store for deletion in finish_operation
        self._top_level_model_roots = [obj for obj in source_objects if obj.parent is None]
        if not self._top_level_model_roots:
            self.report({'ERROR'}, "No top-level model roots found in imported objects. Cannot create grid.")
            return {'CANCELLED'}

        # Calculate grid center offset
        self._grid_x = DUPLICATION_GRID_X
        self._grid_y = DUPLICATION_GRID_Y
        self._spacing_x = SPACING_X
        self._spacing_y = SPACING_Y
        self._start_x = -((self._grid_x - 1) * self._spacing_x) / 2
        self._start_y = -((self._grid_y - 1) * self._spacing_y) / 2
        self._total_cells = self._grid_x * self._grid_y

        # Create main grid collection
        self._grid_collection = bpy.data.collections.new("Background_Grid")
        bpy.context.scene.collection.children.link(self._grid_collection)

        # Create master parent empty
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=BACKGROUND_GLOBAL_LOCATION)
        self._grid_parent = bpy.context.active_object
        self._grid_parent.name = "Background_Grid_Master"
        self._grid_parent.scale = (BACKGROUND_GLOBAL_SCALE, BACKGROUND_GLOBAL_SCALE, BACKGROUND_GLOBAL_SCALE)

        # Move grid parent to grid collection
        bpy.context.collection.objects.unlink(self._grid_parent)
        self._grid_collection.objects.link(self._grid_parent)

        # Initialize progress tracking
        self._current_i = 0
        self._current_j = 0
        context.window_manager.progress_begin(0, self._total_cells)

        # Start the modal timer
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        
        print_debug_info("Operator execute: Starting modal processing.")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'TIMER':
            # Process a batch of grid cells
            cells_processed_this_batch = 0
            for _ in range(BATCH_SIZE):
                if self._current_i >= self._grid_x:
                    # All rows processed, break from batch loop
                    break 

                # Calculate position for this specific grid cell
                pos_x = self._start_x + self._current_i * self._spacing_x
                pos_y = self._start_y + self._current_j * self._spacing_y

                instance_name_base = f"Grid_{self._current_i:02d}_{self._current_j:02d}"
                
                # Create an empty object for this grid cell instance
                bpy.ops.object.empty_add(type='PLAIN_AXES', location=(pos_x, pos_y, 0))
                grid_cell_parent = bpy.context.active_object
                grid_cell_parent.name = f"{instance_name_base}_Cell_Parent"
                
                # Move this cell's parent empty to the 'Background_Grid' collection
                for coll in list(grid_cell_parent.users_collection):
                    coll.objects.unlink(grid_cell_parent)
                self._grid_collection.objects.link(grid_cell_parent)
                
                # Parent this cell's empty to the overall grid master parent
                grid_cell_parent.parent = self._grid_parent
                grid_cell_parent.matrix_parent_inverse = self._grid_parent.matrix_world.inverted()

                # Duplicate each top-level model root for this grid cell
                for obj_to_copy_index, obj_to_copy in enumerate(self._top_level_model_roots):
                    new_instance_root_name_prefix = f"{instance_name_base}_Model_{obj_to_copy_index}"
                    
                    # Use the custom recursive duplication function
                    duplicated_root_obj = duplicate_object_with_hierarchy(
                        obj_to_copy, new_instance_root_name_prefix
                    )
                    
                    # Link the entire duplicated hierarchy to the grid collection
                    link_object_and_hierarchy_to_collection(duplicated_root_obj, self._grid_collection)

                    duplicated_root_obj.parent = grid_cell_parent
                    duplicated_root_obj.location = (0, 0, 0)
                    duplicated_root_obj.rotation_euler = (0, 0, 0) 

                cells_processed_this_batch += 1
                context.window_manager.progress_update(self._current_i * self._grid_y + self._current_j + 1)

                # Move to the next grid cell
                self._current_j += 1
                if self._current_j >= self._grid_y:
                    self._current_j = 0
                    self._current_i += 1
                
                if self._current_i >= self._grid_x:
                    # All cells processed
                    break

            # Check if all cells are processed
            if self._current_i >= self._grid_x:
                print_debug_info("Operator modal: All grid cells processed. Finishing.")
                self.finish_operation(context)
                return {'FINISHED'}
            
            # Request redraw to update UI
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type == 'ESC':
            print_debug_info("Operator modal: Operation cancelled by user.")
            self.report({'WARNING'}, "Background grid generation cancelled.")
            self.finish_operation(context)
            return {'CANCELLED'}

        return {'PASS_THROUGH'} # Allow other events to pass through

    def invoke(self, context, event):
        # This method is called when the operator is invoked (e.g., from main())
        # We start the operator here, but the main work happens in execute and modal.
        return self.execute(context)

    def finish_operation(self, context):
        # Clean up after the operation is finished or cancelled
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        
        context.window_manager.progress_end()

        # Delete original imported objects
        print_debug_info("Finishing operation: Deleting original imported top-level model roots from scene...")
        bpy.ops.object.select_all(action='DESELECT')
        
        if self._original_source_objects: # Use the stored original source objects
            objects_to_delete = []
            for obj_root in self._top_level_model_roots: # Iterate through the identified roots
                # Get the object from the scene by its current name to ensure it's still valid
                scene_obj = bpy.data.objects.get(obj_root.name) 
                if scene_obj: # Check if the object still exists in the scene
                    scene_obj.select_set(True)
                    objects_to_delete.append(scene_obj) 

            if objects_to_delete: 
                bpy.ops.object.delete()
                print_debug_info("Original imported top-level model roots deleted successfully.")
            else:
                print_debug_info("No original top-level model roots found to delete during cleanup.")
        else:
            print_debug_info("Original source objects not available for deletion during cleanup.")


        # Animate if enabled
        if ANIMATE_BACKGROUND and self._grid_parent:
            print_debug_info("Finishing operation: Adding animation.")
            animate_background(
                self._grid_parent,
                BACKGROUND_ANIMATION_START_FRAME,
                BACKGROUND_ANIMATION_END_FRAME,
                BACKGROUND_MOVE_DISTANCE_X,
                BACKGROUND_MOVE_DISTANCE_Y,
                BACKGROUND_MOVE_DISTANCE_Z
            )
        else:
            print_debug_info("Finishing operation: Skipping animation (disabled or no grid parent).")

        # Save template if enabled
        if SAVE_TEMPLATE_BLEND:
            print_debug_info("Finishing operation: Saving template.")
            template_dir = os.path.dirname(TEMPLATE_SAVE_PATH)
            if not os.path.exists(template_dir):
                os.makedirs(template_dir)
            
            bpy.ops.file.pack_all()
            bpy.ops.wm.save_as_mainfile(filepath=TEMPLATE_SAVE_PATH, compress=True)
            print_debug_info(f"Template saved to: {TEMPLATE_SAVE_PATH}")
        else:
            print_debug_info("Finishing operation: Skipping template save (disabled).")

        print("="*50)
        print("BLENDER BACKGROUND GENERATION COMPLETE!")
        print("="*50)
        print(f"Generated Grid size: {DUPLICATION_GRID_X}x{DUPLICATION_GRID_Y}")
        print(f"Model Spacing: {SPACING_X} (X) x {SPACING_Y} (Y)")
        print(f"Animation: {'Enabled' if ANIMATE_BACKGROUND else 'Disabled'}")
        print("Check the 'Background_Grid' collection in the outliner!")


def register():
    bpy.utils.register_class(BackgroundGridGeneratorOperator)

def unregister():
    bpy.utils.unregister_class(BackgroundGridGeneratorOperator)

def main():
    """
    Main function to orchestrate the background generation.
    Registers and runs the modal operator.
    """
    print("="*50)
    print("STARTING BLENDER BACKGROUND GENERATION SCRIPT (Modal)")
    print("="*50)
    
    # Ensure the operator is registered before calling it
    try:
        bpy.utils.register_class(BackgroundGridGeneratorOperator)
    except ValueError:
        # Already registered, unregister and re-register to ensure latest version
        bpy.utils.unregister_class(BackgroundGridGeneratorOperator)
        bpy.utils.register_class(BackgroundGridGeneratorOperator)

    # Call the operator to start the process
    bpy.ops.object.background_grid_generator('INVOKE_DEFAULT')


if __name__ == "__main__":
    main()
