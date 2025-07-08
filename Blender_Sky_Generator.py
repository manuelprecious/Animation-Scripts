import bpy
import os
import traceback

# --- USER CONFIGURATION: Sky Model Settings ---
SKY_MODEL_PATH = r"G:\Models\sky_pano_-_milkyway\scene.gltf" # <-- IMPORTANT: Set your actual sky model path
SKY_MODEL_TYPE = "GLTF" # e.g., "GLTF", "OBJ", "FBX"

SKY_GLOBAL_LOCATION = (0, 0, 0) # Center the sky on the world origin
SKY_GLOBAL_ROTATION_EULER = (0, 0, 0) # Initial rotation (X, Y, Z in radians)
SKY_GLOBAL_SCALE = (1000.0, 1000.0, 1000.0) # Make it very large to encompass the scene

ROTATION_SPEED_DEGREES_PER_SECOND = 5 # Very slow rotation, e.g., 0.1 degrees per second

# Control whether to rebuild the sky if it already exists
REBUILD_SKY_ON_RUN = False # Set to False if you want to preserve existing sky setup

# --- END USER CONFIGURATION ---

# --- INTERNAL SCRIPT CONSTANTS ---
SKY_COLLECTION_NAME = "Sky_Models"
SKY_MASTER_EMPTY_NAME = "Sky_Master"
# --- END INTERNAL SCRIPT CONSTANTS ---

def print_debug_info(message):
    """Helper function to print debug information."""
    print(f"[DEBUG] {message}")

def import_model(filepath, file_type, target_collection):
    """
    Imports a model into the specified collection.
    Returns the top-level imported objects.
    """
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return None

    print_debug_info(f"Importing sky model: {filepath}")

    existing_objects = {obj.name for obj in bpy.data.objects}

    try:
        # Set neutral active collection
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.active_layer_collection = (
            bpy.context.view_layer.layer_collection
        )

        import_ops = {
            "GLTF": bpy.ops.import_scene.gltf,
            "OBJ": bpy.ops.import_scene.obj,
            "FBX": bpy.ops.import_scene.fbx,
        }
        if file_type.upper() not in import_ops:
            print(f"Unsupported file type: {file_type}")
            return None

        import_ops[file_type.upper()](filepath=filepath)

        new_objects = [
            obj for obj in bpy.data.objects if obj.name not in existing_objects
        ]
        if not new_objects:
            print("No objects imported for the sky.")
            return None

        # Link new objects to the target collection and unlink from others
        for obj in new_objects:
            # Unlink from scene collection if it's there by default
            if bpy.context.scene.collection.objects.get(obj.name):
                bpy.context.scene.collection.objects.unlink(obj)

            # Link to the target collection
            if obj.name not in target_collection.objects:
                target_collection.objects.link(obj)

        print_debug_info(f"Imported {len(new_objects)} sky objects into '{target_collection.name}'.")
        return [obj for obj in new_objects if obj.parent is None] # Return top-level objects

    except Exception as e:
        print(f"Sky model import failed: {str(e)[:200]}")
        traceback.print_exc()
        return None

class SkyRotatorOperator(bpy.types.Operator):
    """Blender Operator to import a sky model and animate its rotation."""
    bl_idname = "object.sky_rotator"
    bl_label = "Setup Rotating Sky"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        print_debug_info("Operator execute: Initializing rotating sky setup.")

        bpy.ops.object.select_all(action="DESELECT")

        # Get or create the Sky Collection
        sky_col = bpy.data.collections.get(SKY_COLLECTION_NAME)
        if not sky_col:
            sky_col = bpy.data.collections.new(SKY_COLLECTION_NAME)
            bpy.context.scene.collection.children.link(sky_col)

        # Get or create the Master Empty for the sky
        sky_master_empty = bpy.data.objects.get(SKY_MASTER_EMPTY_NAME)

        if sky_master_empty and REBUILD_SKY_ON_RUN:
            print_debug_info(f"Rebuilding sky: Deleting existing '{SKY_MASTER_EMPTY_NAME}' and its children.")
            # Select the master empty and its children, then delete
            bpy.ops.object.select_all(action="DESELECT")
            sky_master_empty.select_set(True)
            bpy.context.view_layer.objects.active = sky_master_empty
            bpy.ops.object.delete(use_global=False, confirm=False) # Delete selected objects

            # Also clear objects from the collection if they are still linked
            for obj in list(sky_col.objects):
                if obj.name != SKY_MASTER_EMPTY_NAME: # Should already be deleted by parent-child deletion
                    bpy.data.objects.remove(obj, do_unlink=True)
            sky_master_empty = None # Reset to ensure creation below

        if not sky_master_empty:
            print_debug_info(f"Creating new '{SKY_MASTER_EMPTY_NAME}' for sky.")
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=SKY_GLOBAL_LOCATION)
            sky_master_empty = bpy.context.active_object
            sky_master_empty.name = SKY_MASTER_EMPTY_NAME
            sky_master_empty.location = SKY_GLOBAL_LOCATION
            sky_master_empty.rotation_euler = SKY_GLOBAL_ROTATION_EULER
            sky_master_empty.scale = SKY_GLOBAL_SCALE

            # Link master empty to the sky collection
            # Ensure it's only in this collection or scene, unlink from default scene collection if needed
            if bpy.context.scene.collection.objects.get(sky_master_empty.name):
                bpy.context.scene.collection.objects.unlink(sky_master_empty)
            if sky_master_empty.name not in sky_col.objects:
                sky_col.objects.link(sky_master_empty)

        # Import and parent sky model to the master empty
        top_level_sky_objects = import_model(SKY_MODEL_PATH, SKY_MODEL_TYPE, sky_col)

        if top_level_sky_objects:
            for obj in top_level_sky_objects:
                obj.parent = sky_master_empty
                # Keep local transform at identity relative to parent
                obj.location = (0,0,0)
                obj.rotation_euler = (0,0,0)
                obj.scale = (1,1,1)
                # Apply initial transform from master empty to objects, then clear master empty's scale/rot
                # This ensures the model itself has the correct scale/rotation, and the empty is for animation only
                # This is important if you want to scale/rotate the empty later without affecting internal object scale.
                # However, for a simple sky, applying the scale/rot to the master empty is often sufficient.
                # For this script, we'll keep the scale/rotation on the master empty for ease of animation.
                # If your model has its own scale you want to preserve relative to the empty's scale,
                # you might need to adjust this more carefully.

                # Make sure the object is in the Sky_Models collection
                if sky_col not in obj.users_collection:
                    sky_col.objects.link(obj)

        print_debug_info("Applying animation to sky master empty.")
        # --- Animation Setup ---
        # Ensure we are at frame 1 for keyframe insertion
        context.scene.frame_current = context.scene.frame_start

        # Calculate rotation for end frame
        # Blender uses radians for rotation properties
        # Total rotation = (degrees_per_second / 360) * total_frames_in_animation * 2 * pi
        # Or simpler: total_rotation_radians = degrees_per_second * (total_frames_in_animation / context.scene.render.fps) * (math.pi / 180)
        import math
        total_frames = context.scene.frame_end - context.scene.frame_start + 1
        total_seconds = total_frames / context.scene.render.fps
        total_rotation_radians = math.radians(ROTATION_SPEED_DEGREES_PER_SECOND * total_seconds)

        # Set keyframes for Z rotation (assuming rotation around Z-axis)
        sky_master_empty.keyframe_insert(data_path="rotation_euler", index=2, frame=context.scene.frame_start) # Z-axis is index 2

        # Move to end frame
        context.scene.frame_current = context.scene.frame_end

        # Apply rotation (add to existing rotation)
        sky_master_empty.rotation_euler.z += total_rotation_radians
        sky_master_empty.keyframe_insert(data_path="rotation_euler", index=2, frame=context.scene.frame_end)

        # Set interpolation to linear for smooth, constant rotation
        fcurves = sky_master_empty.animation_data.action.fcurves
        for fcurve in fcurves:
            if fcurve.data_path == "rotation_euler" and fcurve.array_index == 2:
                for kp in fcurve.keyframe_points:
                    kp.interpolation = 'LINEAR'
                break # Found the Z rotation fcurve

        print_debug_info("Sky rotation animation applied.")

        # Deselect all at the end
        bpy.ops.object.select_all(action="DESELECT")

        self.report({"INFO"}, "Sky setup and animation complete!")
        print("=" * 50)
        print("BLENDER SKY ROTATOR SCRIPT COMPLETE!")
        print("=" * 50)
        print(f"Sky model '{os.path.basename(SKY_MODEL_PATH)}' imported and animated.")
        print(f"Rotation speed: {ROTATION_SPEED_DEGREES_PER_SECOND} degrees/second (around Z-axis).")
        print("Check the 'Sky_Models' collection in your Blender Outliner.")

        return {"FINISHED"}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    bpy.utils.register_class(SkyRotatorOperator)

def unregister():
    bpy.utils.unregister_class(SkyRotatorOperator)

def main():
    """
    Main function to orchestrate the sky setup and animation.
    Registers and runs the operator.
    """
    print("=" * 50)
    print("STARTING BLENDER SKY ROTATOR SCRIPT")
    print("=" * 50)

    try:
        bpy.utils.register_class(SkyRotatorOperator)
    except ValueError:
        # Already registered, unregister and re-register to ensure latest version
        bpy.utils.unregister_class(SkyRotatorOperator)
        bpy.utils.register_class(SkyRotatorOperator)

    # Call the operator to start the process
    bpy.ops.object.sky_rotator("INVOKE_DEFAULT")

if __name__ == "__main__":
    main()