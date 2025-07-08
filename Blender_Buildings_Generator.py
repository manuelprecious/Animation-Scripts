import bpy
import os
import mathutils
import traceback
import time

# --- USER CONFIGURATION: Background Grid Settings ---
MODEL_PATH = r"G:\Models\asian_themed_low_poly_night_city_buildings\scene.gltf"
MODEL_TYPE = "GLTF"

DUPLICATION_GRID_X = 25
DUPLICATION_GRID_Y = 3

SPACING_X = 300.0
SPACING_Y = 400.0

BACKGROUND_GLOBAL_LOCATION = (0, -50, 0)  # World location for background grid
BACKGROUND_GLOBAL_SCALE_X = 0.002
BACKGROUND_GLOBAL_SCALE_Y = 0.002
BACKGROUND_GLOBAL_SCALE_Z = 0.010

# Control whether to rebuild existing grid
REBUILD_BACKGROUND_GRID_ON_RUN = False

# Batch processing settings for UI responsiveness
BATCH_SIZE = 5  # Grid cells per UI update

# Template export settings
SAVE_TEMPLATE_BLEND = False
TEMPLATE_SAVE_PATH = r"C:\BlenderTemplates\MyBackgroundTemplate.blend"

# --- END USER CONFIGURATION ---

# --- INTERNAL SCRIPT CONSTANTS ---
BACKGROUND_SOURCE_COLLECTION_NAME = "Background_Source_Models"
MASTER_GRID_COLLECTION_NAME = "Background_Grid_Master"
GRID_COLLECTION_NAME = "Background_Grid"
# --- END INTERNAL SCRIPT CONSTANTS ---


def print_debug_info(message):
    """Helper function to print debug information."""
    print(f"[DEBUG] {message}")


def link_object_and_hierarchy_to_collection(obj, target_collection):
    """Memory-optimized version for huge hierarchies"""
    scene_collection = bpy.context.scene.collection
    processed = set()  # Handle circular references

    stack = [obj]
    while stack:
        current = stack.pop()
        if current in processed:
            continue
        processed.add(current)

        # Process current object
        collections = list(current.users_collection)
        for coll in collections:
            if coll not in {scene_collection, target_collection}:
                coll.objects.unlink(current)

        if target_collection not in collections:
            target_collection.objects.link(current)

        # Add children
        stack.extend(child for child in current.children if child not in processed)


def import_and_prepare_model(filepath, file_type, context):
    """
    Imports model and organizes in collection hierarchy
    with proper view layer handling
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return None

    print_debug_info(f"Importing: {filepath}")

    # Store pre-import state
    existing_objects = {obj.name for obj in bpy.data.objects}

    try:
        # Set neutral active collection
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.active_layer_collection = (
            bpy.context.view_layer.layer_collection
        )

        # Perform import
        import_ops = {
            "GLTF": bpy.ops.import_scene.gltf,
            "OBJ": bpy.ops.import_scene.obj,
            "FBX": bpy.ops.import_scene.fbx,
        }
        
        if file_type.upper() not in import_ops:
            print(f"Unsupported type: {file_type}")
            return None
            
        import_ops[file_type.upper()](filepath=filepath)

        # Get newly imported objects
        new_objects = [
            obj for obj in bpy.data.objects if obj.name not in existing_objects
        ]
        if not new_objects:
            print("No objects imported")
            return None

        # Create collection hierarchy
        master_col = bpy.data.collections.get(MASTER_GRID_COLLECTION_NAME)
        if not master_col:
            master_col = bpy.data.collections.new(MASTER_GRID_COLLECTION_NAME)
            context.scene.collection.children.link(master_col)

        source_col = bpy.data.collections.get(BACKGROUND_SOURCE_COLLECTION_NAME)
        if not source_col:
            source_col = bpy.data.collections.new(BACKGROUND_SOURCE_COLLECTION_NAME)
            master_col.children.link(source_col)

        grid_col = bpy.data.collections.get(GRID_COLLECTION_NAME)
        if not grid_col:
            grid_col = bpy.data.collections.new(GRID_COLLECTION_NAME)
            master_col.children.link(grid_col)

        # Link objects to source collection
        for obj in new_objects:
            # Unlink from all collections
            for coll in list(obj.users_collection):
                coll.objects.unlink(obj)
            
            # Link to source collection
            source_col.objects.link(obj)
            
            # Ensure object is in view layer
            if obj.name not in context.view_layer.objects:
                context.view_layer.active_layer_collection.collection.objects.link(obj)

        # Apply transforms without selection
        for obj in new_objects:
            # Save current transform
            location = obj.location.copy()
            rotation = obj.rotation_euler.copy()
            scale = obj.scale.copy()
            
            # Reset transform
            obj.location = (0, 0, 0)
            obj.rotation_euler = (0, 0, 0)
            obj.scale = (1, 1, 1)
            
            # Apply to data if possible
            if obj.type == 'MESH' and obj.data:
                obj.data.transform(obj.matrix_basis)
            
            # Restore transform as identity
            obj.matrix_basis = mathutils.Matrix.Identity(4)
            
            # Apply original transforms at object level
            obj.location = location
            obj.rotation_euler = rotation
            obj.scale = scale

        # Hide collections
        master_col.hide_viewport = True
        master_col.hide_render = True
        source_col.hide_viewport = True
        source_col.hide_render = True

        return [obj for obj in source_col.objects if not obj.parent]

    except Exception as e:
        print(f"Import failed: {str(e)[:200]}")
        traceback.print_exc()
        return None


def duplicate_object_with_hierarchy(obj, new_name_prefix):
    """
    Duplicates object and all children recursively
    Returns new duplicated root object
    """
    parent_map = {}  # Initialize map for top-level call

    def _duplicate_recursive(obj_node, current_name_prefix):
        # Create object copy
        new_obj = obj_node.copy()
        new_obj.name = f"{current_name_prefix}_{obj_node.name}"

        # Copy object data
        if obj_node.data:
            new_obj.data = obj_node.data.copy()
            new_obj.data.name = f"{current_name_prefix}_{obj_node.data.name}"

        # Clear animation data
        new_obj.animation_data_clear()

        # Add mapping
        parent_map[obj_node] = new_obj

        # Recursively duplicate children
        for child in obj_node.children:
            new_child = _duplicate_recursive(child, current_name_prefix)
            new_child.parent = new_obj
            new_child.matrix_parent_inverse = child.matrix_parent_inverse.copy()
        return new_obj

    return _duplicate_recursive(obj, new_name_prefix)


class BackgroundGridGeneratorOperator(bpy.types.Operator):
    """Generate background grid of duplicated models in batches"""
    bl_idname = "object.background_grid_generator"
    bl_label = "Generate Background Grid"
    bl_options = {"REGISTER", "UNDO"}

    # Operator state properties
    _timer = None
    _current_i = 0
    _current_j = 0
    _total_cells = 0
    _grid_parent = None
    _grid_collection = None
    _top_level_model_roots = None
    _source_collection = None
    _start_x = 0.0
    _start_y = 0.0
    _spacing_x = 0.0
    _spacing_y = 0.0
    _grid_x = 0
    _grid_y = 0

    def execute(self, context):
        print_debug_info("Initializing background grid generation")
        bpy.ops.object.select_all(action="DESELECT")  # Clear selection

        # Get/create source collection
        self._source_collection = bpy.data.collections.get(
            BACKGROUND_SOURCE_COLLECTION_NAME
        )
        if not self._source_collection:
            self._source_collection = bpy.data.collections.new(
                BACKGROUND_SOURCE_COLLECTION_NAME
            )
            
        self._source_collection.hide_viewport = True
        self._source_collection.hide_render = True

        # Check/import source objects
        if not self._source_collection.objects:
            print_debug_info("Importing model")
            self._top_level_model_roots = import_and_prepare_model(
                MODEL_PATH, MODEL_TYPE, context
            )
            if not self._top_level_model_roots:
                self.report(
                    {"ERROR"}, 
                    "Failed to import background model source"
                )
                return {"CANCELLED"}
        else:
            print_debug_info("Using existing source objects")
            self._top_level_model_roots = [
                obj for obj in self._source_collection.objects 
                if obj.parent is None
            ]
            if not self._top_level_model_roots:
                self.report(
                    {"ERROR"},
                    "No top-level objects in source collection"
                )
                return {"CANCELLED"}

        # Get master collection
        master_col = bpy.data.collections.get(MASTER_GRID_COLLECTION_NAME)
        if not master_col:
            master_col = bpy.data.collections.new(MASTER_GRID_COLLECTION_NAME)
            context.scene.collection.children.link(master_col)
            master_col.hide_viewport = True
            master_col.hide_render = True

        # Ensure source collection is in master collection
        if self._source_collection.name not in master_col.children:
            master_col.children.link(self._source_collection)

        # Get grid collection
        grid_col = bpy.data.collections.get(GRID_COLLECTION_NAME)
        if not grid_col:
            grid_col = bpy.data.collections.new(GRID_COLLECTION_NAME)
            master_col.children.link(grid_col)
        self._grid_collection = grid_col

        # Check existing grid parent
        existing_grid_parent = bpy.data.objects.get("Background_Grid_Master")

        # Determine rebuild strategy
        should_rebuild = REBUILD_BACKGROUND_GRID_ON_RUN

        if existing_grid_parent:
            # Check for existing grid content
            has_existing_grid_content = any(
                obj != existing_grid_parent 
                for obj in self._grid_collection.objects
            )

            if has_existing_grid_content and not should_rebuild:
                print_debug_info("Preserving existing grid")
                self.report(
                    {"INFO"},
                    "Background exists. Set REBUILD_BACKGROUND_GRID_ON_RUN=True"
                )
                self._grid_parent = existing_grid_parent
                self.finish_operation(context)
                return {"FINISHED"}
            else:
                print_debug_info("Clearing existing grid for rebuild")
                self._grid_parent = existing_grid_parent

                # Clear existing objects in grid collection
                objects_to_delete = []
                for obj in list(self._grid_collection.objects):
                    if obj == self._grid_parent:  # Keep master parent
                        continue

                    # Check collection links
                    exclusive_to_grid = True
                    for coll in obj.users_collection:
                        if (coll != self._grid_collection and 
                            coll != context.scene.collection):
                            exclusive_to_grid = False
                            break

                    if exclusive_to_grid:
                        objects_to_delete.append(obj)
                    else:
                        self._grid_collection.objects.unlink(obj)

                # Delete objects
                for obj_to_delete in objects_to_delete:
                    bpy.data.objects.remove(obj_to_delete, do_unlink=True)
        else:
            print_debug_info("Creating new background grid")

            # Create master parent empty
            bpy.ops.object.empty_add(
                type="PLAIN_AXES", 
                location=BACKGROUND_GLOBAL_LOCATION
            )
            self._grid_parent = context.active_object
            self._grid_parent.name = "Background_Grid_Master"
            self._grid_parent.scale = (
                BACKGROUND_GLOBAL_SCALE_X,
                BACKGROUND_GLOBAL_SCALE_Y,
                BACKGROUND_GLOBAL_SCALE_Z,
            )

        # Ensure grid parent is in the grid collection
        if self._grid_parent.name not in self._grid_collection.objects:
            self._grid_collection.objects.link(self._grid_parent)

        # Remove from other collections
        for coll in list(self._grid_parent.users_collection):
            if coll != self._grid_collection:
                coll.objects.unlink(self._grid_parent)

        # Grid configuration
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

        # Start modal timer
        self._timer = context.window_manager.event_timer_add(
            0.01, 
            window=context.window
        )
        context.window_manager.modal_handler_add(self)

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "TIMER":
            # Process batch of grid cells
            for _ in range(BATCH_SIZE):
                if self._current_i >= self._grid_x:
                    print_debug_info("All grid cells processed")
                    self.finish_operation(context)
                    return {"FINISHED"}

                # Calculate grid position
                pos_x = self._start_x + self._current_i * self._spacing_x
                pos_y = self._start_y + self._current_j * self._spacing_y
                instance_name_base = f"Grid_{self._current_i:02d}_{self._current_j:02d}"

                # Create grid cell parent
                bpy.ops.object.empty_add(
                    type="PLAIN_AXES", 
                    location=(pos_x, pos_y, 0)
                )
                grid_cell_parent = context.active_object
                grid_cell_parent.name = f"{instance_name_base}_Cell_Parent"

                # Link to collection and view layer
                self._grid_collection.objects.link(grid_cell_parent)
                if grid_cell_parent.name not in context.view_layer.objects:
                    context.view_layer.active_layer_collection.collection.objects.link(grid_cell_parent)

                # Parent to master grid
                grid_cell_parent.parent = self._grid_parent
                grid_cell_parent.matrix_parent_inverse = (
                    self._grid_parent.matrix_world.inverted()
                )

                # Duplicate models for this cell
                for idx, obj_to_copy in enumerate(self._top_level_model_roots):
                    new_name_prefix = f"{instance_name_base}_Model_{idx}"
                    duplicated_root = duplicate_object_with_hierarchy(
                        obj_to_copy, 
                        new_name_prefix
                    )

                    # Link and parent
                    self._grid_collection.objects.link(duplicated_root)
                    if duplicated_root.name not in context.view_layer.objects:
                        context.view_layer.active_layer_collection.collection.objects.link(duplicated_root)
                    duplicated_root.parent = grid_cell_parent
                    duplicated_root.location = (0, 0, 0)
                    duplicated_root.rotation_euler = (0, 0, 0)

                # Update progress
                context.window_manager.progress_update(
                    self._current_i * self._grid_y + self._current_j + 1
                )

                # Move to next cell
                self._current_j += 1
                if self._current_j >= self._grid_y:
                    self._current_j = 0
                    self._current_i += 1

            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        elif event.type == "ESC":
            print_debug_info("Operation cancelled by user")
            self.report({"WARNING"}, "Generation cancelled")
            self.finish_operation(context)
            return {"CANCELLED"}

        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        return self.execute(context)

    def finish_operation(self, context):
        # Cleanup
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

        context.window_manager.progress_end()

        # Set viewport clip distance
        try:
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    for space in area.spaces:
                        if space.type == "VIEW_3D":
                            space.clip_end = 100000
                            print("Viewport clip distance set to 100,000")
                            break
                    break
        except Exception as e:
            print(f"Clip distance error: {e}")

        # Save template if enabled
        if SAVE_TEMPLATE_BLEND:
            print_debug_info("Saving template")
            template_dir = os.path.dirname(TEMPLATE_SAVE_PATH)
            if not os.path.exists(template_dir):
                os.makedirs(template_dir)

            bpy.ops.file.pack_all()
            bpy.ops.wm.save_as_mainfile(
                filepath=TEMPLATE_SAVE_PATH, 
                compress=True
            )
            print_debug_info(f"Template saved: {TEMPLATE_SAVE_PATH}")

        bpy.ops.object.select_all(action="DESELECT")  # Final cleanup

        print("=" * 50)
        print("BACKGROUND GRID GENERATION COMPLETE!")
        print("=" * 50)
        print(f"Grid size: {DUPLICATION_GRID_X}x{DUPLICATION_GRID_Y}")
        print(f"Spacing: {SPACING_X} (X) x {SPACING_Y} (Y)")
        print(f"Check '{MASTER_GRID_COLLECTION_NAME}' collection hierarchy")


def register():
    bpy.utils.register_class(BackgroundGridGeneratorOperator)


def unregister():
    bpy.utils.unregister_class(BackgroundGridGeneratorOperator)


def main():
    """Main function to orchestrate background generation"""
    print("=" * 50)
    print("STARTING BACKGROUND GRID GENERATOR")
    print("=" * 50)

    # Ensure operator registration
    try:
        bpy.utils.register_class(BackgroundGridGeneratorOperator)
    except ValueError:
        bpy.utils.unregister_class(BackgroundGridGeneratorOperator)
        bpy.utils.register_class(BackgroundGridGeneratorOperator)

    # Start the process
    bpy.ops.object.background_grid_generator("INVOKE_DEFAULT")


if __name__ == "__main__":
    main()