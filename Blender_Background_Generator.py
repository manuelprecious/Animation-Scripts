import bpy
import os
import mathutils
import traceback
import time

# --- USER CONFIGURATION: Background Grid Settings ---
MODEL_PATH = r"G:\Models\asian_themed_low_poly_night_city_buildings\scene.gltf"
MODEL_TYPE = 'GLTF'

DUPLICATION_GRID_X = 5
DUPLICATION_GRID_Y = 3

SPACING_X = 30.0
SPACING_Y = 40.0

BACKGROUND_GLOBAL_LOCATION = (0, -50, 0) # World location for the entire background grid if created new
BACKGROUND_GLOBAL_SCALE = 1.0

ANIMATE_BACKGROUND = True
BACKGROUND_ANIMATION_START_FRAME = 1
BACKGROUND_ANIMATION_END_FRAME = 250
BACKGROUND_MOVE_DISTANCE_X = 0.0
BACKGROUND_MOVE_DISTANCE_Y = 50.0 # Example: moves 50 units along Y-axis
BACKGROUND_MOVE_DISTANCE_Z = 0.0

# NEW CONFIGURATION: Control whether to rebuild the grid if it already exists
# Set to True to force a complete rebuild (clears existing grid objects).
# Set to False to preserve existing grid objects and their transformations on subsequent runs.
REBUILD_BACKGROUND_GRID_ON_RUN = False # <--- IMPORTANT CHANGE

# Batch processing settings for UI responsiveness
BATCH_SIZE = 5 # Number of grid cells to process per UI update cycle. Adjust based on performance.

# Template export settings (for this script only)
SAVE_TEMPLATE_BLEND = False
TEMPLATE_SAVE_PATH = r"C:\BlenderTemplates\MyBackgroundTemplate.blend"

# --- END USER CONFIGURATION ---

# --- INTERNAL SCRIPT CONSTANTS ---
BACKGROUND_SOURCE_COLLECTION_NAME = "Background_Source_Models" # Collection to hold the original imported model
# --- END INTERNAL SCRIPT CONSTANTS ---


def print_debug_info(message):
    """Helper function to print debug information."""
    print(f"[DEBUG] {message}")


def link_object_and_hierarchy_to_collection(obj, target_collection):
    """
    Links an object and its entire hierarchy to a specified collection,
    unlinking them from any other user-created collections first.
    """
    all_hierarchy_objects = []
    def get_all_children_recursive(node):
        all_hierarchy_objects.append(node)
        for child in node.children:
            get_all_children_recursive(child)
    get_all_children_recursive(obj)

    for node_obj in all_hierarchy_objects:
        # Unlink from all collections it's currently in, UNLESS it's the scene collection
        # or the target collection itself.
        for coll in list(node_obj.users_collection):
            if coll != bpy.context.scene.collection and coll != target_collection:
                coll.objects.unlink(node_obj)
            
        # Link to the target collection if not already there
        if node_obj.name not in target_collection.objects: 
            target_collection.objects.link(node_obj)


def import_and_prepare_model(filepath, file_type):
    """
    Imports a 3D model, applies its transformations, and ensures its original objects
    are placed into a specific source collection and that collection is hidden.
    Returns the top-level objects within the source collection for duplication.
    """
    if not os.path.exists(filepath):
        print(f"Error: Model file NOT found at specified path: {filepath}")
        return None

    print_debug_info(f"Importing model from: {filepath} (Type: {file_type})")

    # Get existing collections and objects before import to identify newly created ones
    collections_before_import = set(bpy.data.collections.keys())
    object_names_before_import = {obj.name for obj in bpy.data.objects}

    try:
        # Important: Set active collection to something neutral before import to avoid linking
        # newly imported objects to an unintended active collection.
        if bpy.context.scene.collection.name in bpy.data.collections:
            bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection
            bpy.ops.object.select_all(action='DESELECT') # Deselect all to ensure no active objects affect import

        # Perform the import
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

        print_debug_info(f"Found {len(newly_imported_objects)} newly imported objects after import operation.")

        if not newly_imported_objects:
            print("Error: No objects were imported or identified. Check file path and type.")
            return None

        # Find new collections created by the importer (e.g., 'scene', 'BACKGROUND_CITY_SKYLINE.fbx')
        new_collections_from_import = [
            bpy.data.collections[name] for name in bpy.data.collections.keys() 
            if name not in collections_before_import and bpy.data.collections[name].users > 0
        ]
        
        # Ensure the "Background_Source_Models" collection exists
        source_collection = bpy.data.collections.get(BACKGROUND_SOURCE_COLLECTION_NAME)
        if not source_collection:
            source_collection = bpy.data.collections.new(BACKGROUND_SOURCE_COLLECTION_NAME)
            bpy.context.scene.collection.children.link(source_collection)
            
        # Move all newly imported objects to the script's source collection
        for obj in newly_imported_objects:
            # Unlink from all current collections, including the temporary import one
            for coll in list(obj.users_collection):
                coll.objects.unlink(obj)
            # Link to our designated source collection
            source_collection.objects.link(obj)

        # Clean up the temporary import collections if they are now empty
        for temp_coll in new_collections_from_import:
            # Ensure it's not our source collection, and it's not the scene's master collection,
            # and it has no objects linked anymore.
            if temp_coll.name != source_collection.name and not temp_coll.objects and temp_coll.name != "Collection":
                print_debug_info(f"Removing empty auto-generated collection: {temp_coll.name}")
                # Unlink from scene master collection before deleting
                if temp_coll.name in bpy.context.scene.collection.children:
                    bpy.context.scene.collection.children.unlink(temp_coll)
                bpy.data.collections.remove(temp_coll)

        # Apply transformations to the objects within the source collection
        print_debug_info("Applying transformations to the imported model's objects...")
        bpy.ops.object.select_all(action='DESELECT')
        for obj in newly_imported_objects:
            obj.select_set(True)
            
        if newly_imported_objects:
            bpy.context.view_layer.objects.active = newly_imported_objects[0]
            
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.object.select_all(action='DESELECT')
        print_debug_info("Transformations applied to imported model.")

        # Hide the source collection in the viewport and render
        source_collection.hide_viewport = True
        source_collection.hide_render = True
        print_debug_info(f"Source collection '{BACKGROUND_SOURCE_COLLECTION_NAME}' hidden.")

        # Return the top-level objects from the source collection for duplication
        top_level_source_objects = [obj for obj in source_collection.objects if obj.parent is None]
        
        # Print object names for debugging AFTER applying transforms
        for obj in top_level_source_objects:
            print_debug_info(f"Source object: {obj.name} (type: {obj.type}) - Loc:{obj.location} Rot:{obj.rotation_euler} Scale:{obj.scale}")

        return top_level_source_objects

    except Exception as e:
        print(f"Error during model import and preparation: {e}")
        traceback.print_exc()
        return None


def duplicate_object_with_hierarchy(obj, new_name_prefix):
    """
    Duplicates an object and all its children recursively, giving them new names.
    This function ensures that all data (mesh, materials, etc.) is copied.
    It returns the new duplicated root object.
    
    Args:
        obj (bpy.types.Object): The original object to duplicate.
        new_name_prefix (str): A prefix to add to the names of duplicated objects.
    Returns:
        bpy.types.Object: The newly created duplicated root object.
    """
    parent_map = {} # Initialize map for the top-level call

    def _duplicate_recursive(obj_node, current_name_prefix):
        # Create a copy of the object
        new_obj = obj_node.copy()
        new_obj.name = f"{current_name_prefix}_{obj_node.name}"

        # Copy object data (e.g., mesh data, curve data)
        if obj_node.data:
            new_obj.data = obj_node.data.copy()
            new_obj.data.name = f"{current_name_prefix}_{obj_node.data.name}"
            
        # Clear animation data from the duplicate to avoid unintended animations
        new_obj.animation_data_clear()

        # Add the mapping from original to duplicate
        parent_map[obj_node] = new_obj

        # Recursively duplicate children
        for child in obj_node.children:
            new_child = _duplicate_recursive(child, current_name_prefix)
            # Set parent for the duplicated child
            new_child.parent = new_obj 
            # Copy the inverse parent matrix to maintain relative transform
            new_child.matrix_parent_inverse = child.matrix_parent_inverse.copy()
        return new_obj

    return _duplicate_recursive(obj, new_name_prefix)


def animate_background_grid(parent_empty, start_frame, end_frame, move_x, move_y, move_z):
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
    bl_label = "Generate Background Grid"
    bl_options = {'REGISTER', 'UNDO'}

    # Operator properties to store state between modal calls
    _timer = None
    _current_i = 0
    _current_j = 0
    _total_cells = 0
    _grid_parent = None
    _grid_collection = None
    _top_level_model_roots = None
    _source_collection = None # New property to store reference to source collection
    _start_x = 0.0
    _start_y = 0.0
    _spacing_x = 0.0
    _spacing_y = 0.0
    _grid_x = 0
    _grid_y = 0

    def execute(self, context):
        print_debug_info("Operator execute: Initializing background grid generation.")
        
        # Clear selection at the start to avoid unintended operations on existing objects
        bpy.ops.object.select_all(action='DESELECT')

        # Get or create the source collection (where the original model will reside)
        self._source_collection = bpy.data.collections.get(BACKGROUND_SOURCE_COLLECTION_NAME)
        if not self._source_collection:
            self._source_collection = bpy.data.collections.new(BACKGROUND_SOURCE_COLLECTION_NAME)
            bpy.context.scene.collection.children.link(self._source_collection)
        # Ensure it's hidden
        self._source_collection.hide_viewport = True
        self._source_collection.hide_render = True

        # Check if source objects are already in the source collection
        # If not, import and prepare them
        if not self._source_collection.objects:
            print_debug_info("Source objects not found in dedicated source collection. Importing model.")
            self._top_level_model_roots = import_and_prepare_model(MODEL_PATH, MODEL_TYPE)
            if not self._top_level_model_roots:
                self.report({'ERROR'}, "Failed to import or prepare background model source.")
                return {'CANCELLED'}
        else:
            print_debug_info("Using existing source objects from dedicated source collection.")
            self._top_level_model_roots = [obj for obj in self._source_collection.objects if obj.parent is None]
            if not self._top_level_model_roots:
                self.report({'ERROR'}, "No top-level objects found in the source collection. Cannot create grid.")
                return {'CANCELLED'}

        # Check for existing background elements to avoid re-creating master empty
        existing_grid_parent = bpy.data.objects.get("Background_Grid_Master")
        existing_grid_collection = bpy.data.collections.get("Background_Grid")

        # --- MODIFIED LOGIC START ---
        # Determine if we should rebuild the grid or preserve existing one
        should_rebuild = REBUILD_BACKGROUND_GRID_ON_RUN

        if existing_grid_parent and existing_grid_collection:
            # Check if there are actual duplicated models in the grid collection (beyond just the parent empty)
            # This is a heuristic to determine if the grid has been "built"
            has_existing_grid_content = any(obj != existing_grid_parent for obj in existing_grid_collection.objects)

            if has_existing_grid_content and not should_rebuild:
                print_debug_info("Existing 'Background_Grid' found with content. Skipping grid generation to preserve manual changes.")
                self.report({'INFO'}, "Background grid already exists. Set REBUILD_BACKGROUND_GRID_ON_RUN = True to force rebuild.")
                
                # If we're skipping generation, we still need to ensure the parent and collection are set for animation/cleanup
                self._grid_parent = existing_grid_parent
                self._grid_collection = existing_grid_collection
                
                # We still need to call finish_operation to handle animation and template saving
                self.finish_operation(context)
                return {'FINISHED'}
            else:
                print_debug_info("Existing 'Background_Grid' found. Clearing contents to rebuild or it's empty.")
                self._grid_parent = existing_grid_parent
                self._grid_collection = existing_grid_collection
                
                # Clear existing objects within the collection to rebuild the grid
                objects_to_delete = []
                for obj in list(self._grid_collection.objects):
                    if obj == self._grid_parent: # Don't delete the master parent itself
                        continue
                    
                    # Check if the object is only linked to this grid collection or also to the scene collection (which is fine)
                    is_exclusively_in_grid_collection = True
                    for coll in obj.users_collection:
                        if coll != self._grid_collection and coll != bpy.context.scene.collection:
                            is_exclusively_in_grid_collection = False
                            break
                    
                    if is_exclusively_in_grid_collection:
                        objects_to_delete.append(obj)
                    else:
                        # If shared with other *non-scene* collections, just unlink it from Background_Grid
                        self._grid_collection.objects.unlink(obj)
                
                for obj_to_delete in objects_to_delete:
                    bpy.data.objects.remove(obj_to_delete, do_unlink=True)
                
        else: # No existing grid parent or collection found
            print_debug_info("No existing 'Background_Grid' elements found. Creating new.")
            
            # Create main grid collection for background
            self._grid_collection = bpy.data.collections.new("Background_Grid")
            bpy.context.scene.collection.children.link(self._grid_collection)

            # Create master parent empty for background
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=BACKGROUND_GLOBAL_LOCATION)
            self._grid_parent = bpy.context.active_object
            self._grid_parent.name = "Background_Grid_Master"
            self._grid_parent.scale = (BACKGROUND_GLOBAL_SCALE, BACKGROUND_GLOBAL_SCALE, BACKGROUND_GLOBAL_SCALE)

            # Move grid parent to grid collection (ensure it's only in this one or scene)
            for coll in list(self._grid_parent.users_collection):
                if coll != self._grid_collection: # Don't unlink from its own collection or the scene collection
                    coll.objects.unlink(self._grid_parent)
            if self._grid_parent.name not in self._grid_collection.objects:
                self._grid_collection.objects.link(self._grid_parent)
        # --- MODIFIED LOGIC END ---

        # Calculate grid center offset (always calculate based on current settings)
        self._grid_x = DUPLICATION_GRID_X
        self._grid_y = DUPLICATION_GRID_Y
        self._spacing_x = SPACING_X
        self._spacing_y = SPACING_Y
        self._start_x = -((self._grid_x - 1) * self._spacing_x) / 2
        self._start_y = -((self._grid_y - 1) * self._spacing_y) / 2
        self._total_cells = self._grid_x * self._grid_y

        # Initialize progress tracking
        self._current_i = 0
        self._current_j = 0
        context.window_manager.progress_begin(0, self._total_cells)

        # Start the modal timer for background generation
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        
        print_debug_info("Operator execute: Starting modal processing for background grid.")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'TIMER':
            # Process a batch of grid cells
            cells_processed_this_batch = 0
            for _ in range(BATCH_SIZE):
                if self._current_i >= self._grid_x:
                    # All background cells processed
                    print_debug_info("Operator modal: All background grid cells processed. Finishing.")
                    self.finish_operation(context)
                    return {'FINISHED'}

                # Calculate position for this specific grid cell
                pos_x = self._start_x + self._current_i * self._spacing_x
                pos_y = self._start_y + self._current_j * self._spacing_y

                instance_name_base = f"Grid_{self._current_i:02d}_{self._current_j:02d}"
                
                # Create an empty object for this grid cell instance
                bpy.ops.object.empty_add(type='PLAIN_AXES', location=(pos_x, pos_y, 0))
                grid_cell_parent = bpy.context.active_object
                grid_cell_parent.name = f"{instance_name_base}_Cell_Parent"
                
                # Move this cell's parent empty to the 'Background_Grid' collection
                link_object_and_hierarchy_to_collection(grid_cell_parent, self._grid_collection)
                
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
        return self.execute(context)

    def finish_operation(self, context):
        # Clean up after the operation is finished or cancelled
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
            
        context.window_manager.progress_end()

        # Original imported objects (background model) are now persistent in a hidden collection.
        # No explicit deletion is needed here.

        # Animate background if enabled
        if ANIMATE_BACKGROUND and self._grid_parent:
            print_debug_info("Finishing operation: Adding background animation.")
            animate_background_grid(
                self._grid_parent,
                BACKGROUND_ANIMATION_START_FRAME,
                BACKGROUND_ANIMATION_END_FRAME,
                BACKGROUND_MOVE_DISTANCE_X,
                BACKGROUND_MOVE_DISTANCE_Y,
                BACKGROUND_MOVE_DISTANCE_Z
            )
        else:
            print_debug_info("Finishing operation: Skipping background animation (disabled or no grid parent).")

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

        # Deselect all objects at the end, if any are active
        bpy.ops.object.select_all(action='DESELECT')

        print("="*50)
        print("BLENDER BACKGROUND GRID GENERATION COMPLETE!")
        print("="*50)
        print(f"Background Grid size: {DUPLICATION_GRID_X}x{DUPLICATION_GRID_Y}")
        print(f"Background Model Spacing: {SPACING_X} (X) x {SPACING_Y} (Y)")
        print(f"Background Animation: {'Enabled' if ANIMATE_BACKGROUND else 'Disabled'}")
        print("Please check the 'Background_Grid' and 'Background_Source_Models' collections in your Blender Outliner.")


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
    print("STARTING BLENDER BACKGROUND GRID GENERATOR SCRIPT")
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
