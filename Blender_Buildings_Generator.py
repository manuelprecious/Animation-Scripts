import bpy
import os
import mathutils
import traceback
import time

# --- USER CONFIGURATION: Background Grid Settings ---
# IMPORTANT: MODEL_PATH should be an absolute path accessible by Blender.
# On Windows, use raw strings (r"C:\path\to\model.gltf") or double backslashes ("C:\\path\\to\\model.gltf").
# On macOS/Linux, use forward slashes ("/path/to/model.gltf").
MODEL_PATH = r"G:\Models\asian_themed_low_poly_night_city_buildings\scene.gltf"
MODEL_TYPE = "GLTF" # Supported: "GLTF", "OBJ", "FBX"

DUPLICATION_GRID_X = 25 # Number of duplicates along the X-axis
DUPLICATION_GRID_Y = 3  # Number of duplicates along the Y-axis

SPACING_X = 300.0 # Spacing between duplicated models along the X-axis
SPACING_Y = 400.0 # Spacing between duplicated models along the Y-axis

BACKGROUND_GLOBAL_LOCATION = (
    0,
    -50,
    0,
)   # World location for the entire background grid if created new
BACKGROUND_GLOBAL_SCALE_X = 0.002 # Global scale for the X-axis of the entire grid
BACKGROUND_GLOBAL_SCALE_Y = 0.002 # Global scale for the Y-axis of the entire grid
BACKGROUND_GLOBAL_SCALE_Z = 0.010 # Global scale for the Z-axis of the entire grid

# Control whether to rebuild the grid if it already exists.
# Set to True to force a complete rebuild, False to preserve existing grid.
REBUILD_BACKGROUND_GRID_ON_RUN = False

# Batch processing settings for UI responsiveness.
# This controls how many grid cells are processed before updating the UI,
# preventing Blender from freezing during large operations.
BATCH_SIZE = 5  # Number of grid cells to process per UI update cycle

# Template export settings.
# If True, the script will save the current Blender file as a template
# after generating the grid.
SAVE_TEMPLATE_BLEND = False
# Path where the template .blend file will be saved.
TEMPLATE_SAVE_PATH = r"C:\BlenderTemplates\MyBackgroundTemplate.blend"

# --- END USER CONFIGURATION ---

# --- INTERNAL SCRIPT CONSTANTS ---
# Name of the collection that will hold the original imported model.
# This collection is hidden and serves as the source for duplication.
BACKGROUND_SOURCE_COLLECTION_NAME = (
    "Background_Source_Models"
)
# --- END INTERNAL SCRIPT CONSTANTS ---


def print_debug_info(message):
    """Helper function to print debug information to the Blender console."""
    print(f"[DEBUG] {message}")


def link_object_and_hierarchy_to_collection(obj, target_collection):
    """
    Links an object and its entire hierarchy (children, grandchildren, etc.)
    to a specified collection. It first unlinks them from ALL other collections
    to ensure clean and exclusive organization within the target collection.

    Args:
        obj (bpy.types.Object): The root object of the hierarchy to link.
        target_collection (bpy.types.Collection): The collection to link objects to.
    """
    processed = set()  # Set to keep track of already processed objects
    stack = [obj]      # Use a stack for iterative depth-first traversal

    while stack:
        current = stack.pop()
        if current in processed:
            continue # Skip if already processed
        processed.add(current)

        # Unlink from ALL collections it's currently in
        # We iterate over a copy of users_collection because unlinking modifies the original
        for coll in list(current.users_collection):
            coll.objects.unlink(current)

        # Then link ONLY to the target collection if not already linked
        # This ensures objects reside exclusively in the intended collection
        if target_collection not in current.users_collection:
            target_collection.objects.link(current)

        # Add children to the stack for recursive processing
        stack.extend(child for child in current.children if child not in processed)


def import_and_prepare_model(filepath, file_type):
    """
    Imports a 3D model from the given filepath and organizes it into a strict
    Blender collection hierarchy for background generation.

    Hierarchy:
    Scene Collection
    └── Background_Grid_Master (empty object, parent for the entire grid)
        └── Background_Source_Models (hidden collection for original imported models)
            └── Imported Objects (the actual model data)

    Args:
        filepath (str): The absolute path to the 3D model file.
        file_type (str): The type of the model file (e.g., "GLTF", "OBJ", "FBX").

    Returns:
        list[bpy.types.Object]: A list of top-level imported objects (those without parents)
                                within the source collection, or None if import fails.
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return None

    print_debug_info(f"Importing: {filepath}")

    # Store the names of existing objects before import to identify newly imported ones
    existing_objects = {obj.name for obj in bpy.data.objects}

    try:
        # Deselect all objects and set the active collection to the scene collection
        # to ensure imported objects are not linked to an unintended collection initially.
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.active_layer_collection = (
            bpy.context.view_layer.layer_collection
        )

        # Dictionary mapping file types to their corresponding Blender import operators
        import_ops = {
            "GLTF": bpy.ops.import_scene.gltf,
            "OBJ": bpy.ops.import_scene.obj,
            "FBX": bpy.ops.import_scene.fbx,
        }
        if file_type.upper() not in import_ops:
            print(f"Unsupported file type: {file_type}")
            return None
        
        # Execute the appropriate import operator
        import_ops[file_type.upper()](filepath=filepath)

        # Identify newly imported objects by comparing with the pre-import list
        new_objects = [
            obj for obj in bpy.data.objects if obj.name not in existing_objects
        ]
        if not new_objects:
            print("No objects were imported.")
            return None

        # Create or get the master collection for the entire background grid.
        # This collection will contain the source models and the duplicated grid.
        master_col = bpy.data.collections.get("Background_Grid_Master_Collection")
        if not master_col:
            master_col = bpy.data.collections.new("Background_Grid_Master_Collection")
            bpy.context.scene.collection.children.link(master_col)

        # Create or get the source collection, which will hold the original imported model.
        source_col = bpy.data.collections.get(BACKGROUND_SOURCE_COLLECTION_NAME)
        if not source_col:
            source_col = bpy.data.collections.new(BACKGROUND_SOURCE_COLLECTION_NAME)
            master_col.children.link(source_col)  # Link as a child of Background_Grid_Master_Collection

        # Process imported objects in batches for better performance and UI responsiveness.
        batch_size = 50
        for i in range(0, len(new_objects), batch_size):
            batch = new_objects[i : i + batch_size]

            for obj in batch:
                # Completely unlink the object from all existing collections first.
                # This ensures it's only linked to our target source collection.
                for coll in list(obj.users_collection):
                    coll.objects.unlink(obj)

                # Link the object ONLY to our designated source collection.
                source_col.objects.link(obj)

        # Apply transforms (location, rotation, scale) to the imported objects.
        # This resets their transformations while preserving their visual appearance,
        # which is crucial for consistent duplication.
        for obj in new_objects:
            obj.select_set(True) # Select each new object
        if new_objects:
            # Set the first new object as active to allow apply_transform to work
            bpy.context.view_layer.objects.active = new_objects[0]
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.object.select_all(action="DESELECT") # Deselect all after applying transforms

        # Hide both the master collection and the source collection from viewport and render.
        # This keeps the original models out of sight but available for duplication.
        master_col.hide_viewport = True
        master_col.hide_render = True
        source_col.hide_viewport = True
        source_col.hide_render = True

        # Return a list of top-level objects (objects without parents) from the source collection.
        # These are the roots of the model hierarchy that will be duplicated.
        return [obj for obj in source_col.objects if not obj.parent]

    except Exception as e:
        print(f"Import failed: {str(e)[:200]}")
        traceback.print_exc() # Print full traceback for debugging

        # Emergency cleanup: Deselect all objects in case of an error
        bpy.ops.object.select_all(action="DESELECT")
        return None


def duplicate_object_with_hierarchy(obj, new_name_prefix):
    """
    Duplicates an object and all its children iteratively, giving them new names.
    This function ensures that all data (mesh, materials, etc.) is copied
    and the parent-child relationships are maintained in the duplicated hierarchy.

    Args:
        obj (bpy.types.Object): The original root object to duplicate.
        new_name_prefix (str): A prefix to add to the names of all duplicated objects.

    Returns:
        bpy.types.Object: The newly created duplicated root object.
    """
    # Dictionary to map original objects to their newly created duplicates.
    # This is crucial for correctly setting up parent-child relationships in the new hierarchy.
    original_to_duplicate_map = {}
    
    # Stack for iterative traversal (depth-first).
    # Each element is a tuple: (original_object, parent_of_original_object_in_hierarchy)
    # We need the parent to establish the parent-child link in the duplicated hierarchy.
    stack = [(obj, None)] 

    # First pass: Duplicate all objects and their data, and build the mapping.
    while stack:
        original_obj, original_parent = stack.pop()

        if original_obj in original_to_duplicate_map:
            continue # Already processed this object

        # Create a copy of the object itself
        new_obj = original_obj.copy()
        new_obj.name = f"{new_name_prefix}_{original_obj.name}"

        # Copy object data (e.g., mesh data, curve data) if it exists.
        # This makes the duplicated object independent of the original's data.
        if original_obj.data:
            new_obj.data = original_obj.data.copy()
            new_obj.data.name = f"{new_name_prefix}_{original_obj.data.name}"

        # Clear animation data from the duplicate to avoid unintended animations
        new_obj.animation_data_clear()

        # Store the mapping from the original object to its duplicate
        original_to_duplicate_map[original_obj] = new_obj

        # Add children to the stack for processing in the next iterations
        for child in original_obj.children:
            stack.append((child, original_obj)) # Push child and its original parent

    # Second pass: Establish parent-child relationships and copy inverse parent matrices.
    # This needs to be done after all objects are duplicated and mapped.
    for original_obj, new_obj in original_to_duplicate_map.items():
        if original_obj.parent:
            # Set the parent for the newly duplicated child to its duplicated parent
            new_obj.parent = original_to_duplicate_map[original_obj.parent]
            # Copy the inverse parent matrix to maintain the correct relative transform
            new_obj.matrix_parent_inverse = original_obj.matrix_parent_inverse.copy()

    # Return the duplicated root object
    return original_to_duplicate_map[obj]


class BackgroundGridGeneratorOperator(bpy.types.Operator):
    """
    Blender Operator to generate a background grid of duplicated models in batches.
    This operator uses a modal timer to process duplication in chunks,
    keeping the Blender UI responsive for large grids.
    """

    bl_idname = "object.background_grid_generator" # Unique identifier for the operator
    bl_label = "Generate Background Grid"          # Label displayed in Blender's UI
    bl_options = {"REGISTER", "UNDO"}              # Allow registration and undo functionality

    # Operator properties to store state between modal calls (important for batch processing)
    _timer = None                     # Blender timer for modal updates
    _current_i = 0                    # Current X-index in the grid
    _current_j = 0                    # Current Y-index in the grid
    _total_cells = 0                  # Total number of cells in the grid
    _grid_parent = None               # The master empty object parenting the entire grid
    _grid_collection = None           # The collection holding the duplicated grid objects
    _top_level_model_roots = None     # List of top-level objects from the imported source model
    _source_collection = None         # Reference to the collection holding the original source models
    _start_x = 0.0                    # Starting X-coordinate for grid generation
    _start_y = 0.0                    # Starting Y-coordinate for grid generation
    _spacing_x = 0.0                  # X-spacing between grid cells
    _spacing_y = 0.0                  # Y-spacing between grid cells
    _grid_x = 0                       # Grid dimension in X
    _grid_y = 0                       # Grid dimension in Y

    def execute(self, context):
        """
        This method is called when the operator is first executed.
        It initializes the grid generation process.
        """
        print_debug_info("Operator execute: Initializing background grid generation.")

        # Clear selection at the start to avoid unintended operations on existing objects
        bpy.ops.object.select_all(action="DESELECT")

        # Get or create the source collection where the original model will reside.
        self._source_collection = bpy.data.collections.get(
            BACKGROUND_SOURCE_COLLECTION_NAME
        )
        if not self._source_collection:
            self._source_collection = bpy.data.collections.new(
                BACKGROUND_SOURCE_COLLECTION_NAME
            )
            # Link the source collection to the scene's master collection
            bpy.context.scene.collection.children.link(self._source_collection)
        # Ensure the source collection is hidden from viewport and render
        self._source_collection.hide_viewport = True
        self._source_collection.hide_render = True

        # Check if source objects are already present in the source collection.
        # If not, import and prepare them from the specified MODEL_PATH.
        if not self._source_collection.objects:
            print_debug_info(
                "Source objects not found in dedicated source collection. Importing model."
            )
            self._top_level_model_roots = import_and_prepare_model(
                MODEL_PATH, MODEL_TYPE
            )
            if not self._top_level_model_roots:
                self.report(
                    {"ERROR"}, "Failed to import or prepare background model source."
                )
                return {"CANCELLED"}
        else:
            print_debug_info(
                "Using existing source objects from dedicated source collection."
            )
            # If objects exist, retrieve the top-level ones (those without parents)
            self._top_level_model_roots = [
                obj for obj in self._source_collection.objects if obj.parent is None
            ]
            if not self._top_level_model_roots:
                self.report(
                    {"ERROR"},
                    "No top-level objects found in the source collection. Cannot create grid.",
                )
                return {"CANCELLED"}

        # Check for existing background grid elements (master empty and collection).
        existing_grid_parent = bpy.data.objects.get("Background_Grid_Master")
        existing_grid_collection = bpy.data.collections.get("Background_Grid")

        # Determine if we should rebuild the grid based on user configuration.
        should_rebuild = REBUILD_BACKGROUND_GRID_ON_RUN

        if existing_grid_parent and existing_grid_collection:
            # Heuristic to check if the grid collection actually contains duplicated models
            # (i.e., it's not just the parent empty object).
            has_existing_grid_content = any(
                obj != existing_grid_parent for obj in existing_grid_collection.objects
            )

            if has_existing_grid_content and not should_rebuild:
                # If content exists and rebuild is not forced, skip generation.
                print_debug_info(
                    "Existing 'Background_Grid' found with content. Skipping grid generation to preserve manual changes."
                )
                self.report(
                    {"INFO"},
                    "Background grid already exists. Set REBUILD_BACKGROUND_GRID_ON_RUN = True to force rebuild.",
                )

                # Still set the internal references to the existing parent and collection
                # so that finish_operation can handle animation and template saving.
                self._grid_parent = existing_grid_parent
                self._grid_collection = existing_grid_collection

                self.finish_operation(context) # Call finish to handle final steps
                return {"FINISHED"}
            else:
                # If content exists but rebuild is forced, or if the grid is empty, clear it.
                print_debug_info(
                    "Existing 'Background_Grid' found. Clearing contents to rebuild or it's empty."
                )
                self._grid_parent = existing_grid_parent
                self._grid_collection = existing_grid_collection

                # Clear existing objects within the grid collection to prepare for rebuild.
                objects_to_delete = []
                for obj in list(self._grid_collection.objects):
                    if obj == self._grid_parent:
                        continue # Do not delete the master parent itself

                    # If shared, just unlink from Background_Grid, don't delete data
                    # (This logic is now handled more strictly by link_object_and_hierarchy_to_collection
                    # when new objects are added, but for clearing existing, we remove)
                    objects_to_delete.append(obj)

                # Delete the identified objects.
                for obj_to_delete in objects_to_delete:
                    bpy.data.objects.remove(obj_to_delete, do_unlink=True)

        else:  # No existing grid parent or collection found, so create new ones.
            print_debug_info(
                "No existing 'Background_Grid' elements found. Creating new."
            )

            # Create the main grid collection for background objects.
            self._grid_collection = bpy.data.collections.new("Background_Grid")
            bpy.context.scene.collection.children.link(self._grid_collection)

            # Create a master parent empty object for the entire background grid.
            # This allows easy manipulation (move, scale) of the whole grid.
            bpy.ops.object.empty_add(
                type="PLAIN_AXES", location=BACKGROUND_GLOBAL_LOCATION
            )
            self._grid_parent = bpy.context.active_object
            self._grid_parent.name = "Background_Grid_Master"
            # Apply global scale to the master parent empty.
            self._grid_parent.scale = (
                BACKGROUND_GLOBAL_SCALE_X,
                BACKGROUND_GLOBAL_SCALE_Y,
                BACKGROUND_GLOBAL_SCALE_Z,
            )

            # Link the grid parent empty to the 'Background_Grid' collection.
            # Use the stricter linking function to ensure it's only in this collection.
            link_object_and_hierarchy_to_collection(self._grid_parent, self._grid_collection)


        # Calculate grid dimensions and starting coordinates.
        self._grid_x = DUPLICATION_GRID_X
        self._grid_y = DUPLICATION_GRID_Y
        self._spacing_x = SPACING_X
        self._spacing_y = SPACING_Y
        # Calculate the starting X and Y positions to center the grid around the origin.
        self._start_x = -((self._grid_x - 1) * self._spacing_x) / 2
        self._start_y = -((self._grid_y - 1) * self._spacing_y) / 2
        self._total_cells = self._grid_x * self._grid_y

        # Initialize progress tracking for the Blender UI.
        self._current_i = 0 # Reset X-index
        self._current_j = 0 # Reset Y-index
        context.window_manager.progress_begin(0, self._total_cells)

        # Start the modal timer. This will call the `modal` method periodically,
        # allowing the script to process in batches and keep the UI responsive.
        self._timer = context.window_manager.event_timer_add(
            0.01, window=context.window # Timer fires every 0.01 seconds
        )
        context.window_manager.modal_handler_add(self) # Add this operator as a modal handler

        print_debug_info(
            "Operator execute: Starting modal processing for background grid."
        )
        return {"RUNNING_MODAL"} # Indicate that the operator is running in modal mode

    def modal(self, context, event):
        """
        This method is called repeatedly by the modal timer.
        It processes a batch of grid cells in each call.
        """
        if event.type == "TIMER": # Only react to timer events
            cells_processed_this_batch = 0
            # Process up to BATCH_SIZE cells in this iteration
            for _ in range(BATCH_SIZE):
                if self._current_i >= self._grid_x:
                    # All grid cells have been processed.
                    print_debug_info(
                        "Operator modal: All background grid cells processed. Finishing."
                    )
                    self.finish_operation(context) # Perform final cleanup and actions
                    return {"FINISHED"} # Signal that the operator has finished

                # Calculate the world position for the current grid cell.
                pos_x = self._start_x + self._current_i * self._spacing_x
                pos_y = self._start_y + self._current_j * self._spacing_y

                # Generate a unique name for the instance based on its grid coordinates.
                instance_name_base = f"Grid_{self._current_i:02d}_{self._current_j:02d}"

                # Create an empty object to serve as the parent for all duplicated models
                # within this specific grid cell. This allows easy manipulation of each cell.
                bpy.ops.object.empty_add(type="PLAIN_AXES", location=(pos_x, pos_y, 0))
                grid_cell_parent = bpy.context.active_object
                grid_cell_parent.name = f"{instance_name_base}_Cell_Parent"

                # Link this cell's parent empty to the 'Background_Grid' collection.
                # The updated link_object_and_hierarchy_to_collection will ensure it's only here.
                link_object_and_hierarchy_to_collection(
                    grid_cell_parent, self._grid_collection
                )

                # Parent this cell's empty to the overall grid master parent.
                # This ensures the entire grid can be moved/scaled together.
                grid_cell_parent.parent = self._grid_parent
                # Set the inverse parent matrix to maintain the correct relative transform
                # between the cell parent and the master grid parent.
                grid_cell_parent.matrix_parent_inverse = (
                    self._grid_parent.matrix_world.inverted()
                )

                # Duplicate each top-level model root from the source for this grid cell.
                for obj_to_copy_index, obj_to_copy in enumerate(
                    self._top_level_model_roots
                ):
                    new_instance_root_name_prefix = (
                        f"{instance_name_base}_Model_{obj_to_copy_index}"
                    )

                    # Use the custom iterative duplication function to copy the model hierarchy.
                    duplicated_root_obj = duplicate_object_with_hierarchy(
                        obj_to_copy, new_instance_root_name_prefix
                    )

                    # Link the entire duplicated hierarchy (root and its children)
                    # to the 'Background_Grid' collection.
                    # The updated link_object_and_hierarchy_to_collection will ensure it's only here.
                    link_object_and_hierarchy_to_collection(
                        duplicated_root_obj, self._grid_collection
                    )

                    # Parent the duplicated model's root to the current grid cell's parent empty.
                    duplicated_root_obj.parent = grid_cell_parent
                    # Reset its local location/rotation relative to its new parent
                    duplicated_root_obj.location = (0, 0, 0)
                    duplicated_root_obj.rotation_euler = (0, 0, 0)

                cells_processed_this_batch += 1
                # Update the progress bar in the Blender UI.
                context.window_manager.progress_update(
                    self._current_i * self._grid_y + self._current_j + 1
                )

                # Move to the next grid cell (increment column, then row).
                self._current_j += 1
                if self._current_j >= self._grid_y:
                    self._current_j = 0
                    self._current_i += 1

            # Request a redraw of the Blender UI to show progress and newly created objects.
            context.area.tag_redraw()
            return {"RUNNING_MODAL"} # Continue running in modal mode

        elif event.type == "ESC":
            # If the user presses ESC, cancel the operation.
            print_debug_info("Operator modal: Operation cancelled by user.")
            self.report({"WARNING"}, "Background grid generation cancelled.")
            self.finish_operation(context) # Clean up
            return {"CANCELLED"} # Signal cancellation

        return {"PASS_THROUGH"} # Allow other events to be handled by Blender

    def invoke(self, context, event):
        """
        This method is called when the operator is invoked (e.g., from a menu or hotkey).
        It simply calls the execute method to start the process.
        """
        return self.execute(context)

    def finish_operation(self, context):
        """
        Performs final cleanup and actions after the grid generation is finished or cancelled.
        This includes removing the timer, ending the progress bar, setting viewport clip distance,
        and optionally saving a template file.
        """
        # Remove the modal timer if it's still active.
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

        # End the progress bar in the Blender UI.
        context.window_manager.progress_end()

        # === NEW: Set viewport clip distance ===
        # This is important for viewing large background grids, as default clip distance
        # might cut off distant objects.
        try:
            # Iterate through all areas and spaces in the current screen.
            for area in context.screen.areas:
                if area.type == "VIEW_3D": # Find 3D Viewport areas
                    for space in area.spaces:
                        if space.type == "VIEW_3D": # Find 3D Viewport spaces
                            space.clip_end = 100000 # Set the clip end distance to a large value
                            print("Viewport clip distance set to 100,000")
                            break # Found and set, so break from inner loop
                    break # Found and set, so break from outer loop
        except Exception as e:
            print(f"Could not set viewport clip distance: {e}")

        # Save template if the user configuration `SAVE_TEMPLATE_BLEND` is True.
        if SAVE_TEMPLATE_BLEND:
            print_debug_info("Finishing operation: Saving template.")
            template_dir = os.path.dirname(TEMPLATE_SAVE_PATH)
            if not os.path.exists(template_dir):
                os.makedirs(template_dir) # Create directory if it doesn't exist

            # Pack all external data (textures, etc.) into the .blend file.
            bpy.ops.file.pack_all()
            # Save the current Blender file as the template.
            bpy.ops.wm.save_as_mainfile(filepath=TEMPLATE_SAVE_PATH, compress=True)
            print_debug_info(f"Template saved to: {TEMPLATE_SAVE_PATH}")
        else:
            print_debug_info("Finishing operation: Skipping template save (disabled).")

        # Deselect all objects at the end for a clean state.
        bpy.ops.object.select_all(action="DESELECT")

        # Print a completion message to the Blender console.
        print("=" * 50)
        print("BLENDER BACKGROUND GRID GENERATION COMPLETE!")
        print("=" * 50)
        print(f"Background Grid size: {DUPLICATION_GRID_X}x{DUPLICATION_GRID_Y}")
        print(f"Background Model Spacing: {SPACING_X} (X) x {SPACING_Y} (Y)")
        print(
            "Please check the 'Background_Grid' and 'Background_Source_Models' collections in your Blender Outliner."
        )


def register():
    """
    Registers the Blender operator so it can be used within Blender.
    This function is typically called when a script is enabled as an add-on.
    """
    bpy.utils.register_class(BackgroundGridGeneratorOperator)


def unregister():
    """
    Unregisters the Blender operator.
    This function is typically called when an add-on is disabled.
    """
    bpy.utils.unregister_class(BackgroundGridGeneratorOperator)


def main():
    """
    Main function to orchestrate the background generation.
    It ensures the operator is registered and then invokes it.
    """
    print("=" * 50)
    print("STARTING BLENDER BACKGROUND GRID GENERATOR SCRIPT")
    print("=" * 50)

    # Ensure the operator is registered before calling it.
    # This block handles cases where the script might be run multiple times
    # without restarting Blender, preventing "already registered" errors.
    try:
        bpy.utils.register_class(BackgroundGridGeneratorOperator)
    except ValueError:
        # If already registered, unregister and re-register to ensure the latest version of the script is used.
        bpy.utils.unregister_class(BackgroundGridGeneratorOperator)
        bpy.utils.register_class(BackgroundGridGeneratorOperator)

    # Call the operator to start the background grid generation process.
    # "INVOKE_DEFAULT" tells Blender to run the operator in its default mode,
    # which for a modal operator means starting the modal loop.
    bpy.ops.object.background_grid_generator("INVOKE_DEFAULT")


if __name__ == "__main__":
    # This block ensures that `main()` is called only when the script is run directly
    # (e.g., from Blender's text editor or as an add-on), not when it's imported as a module.
    main()
