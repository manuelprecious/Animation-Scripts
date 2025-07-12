import bpy
import math
from mathutils import Vector, Matrix, Quaternion
import mathutils
from mathutils.bvhtree import BVHTree
import traceback
from random import uniform, choice

# Global Blender version for compatibility checks
MAJOR_VERSION, MINOR_VERSION, SUB_VERSION = bpy.app.version

# --- Helper Functions ---

def print_debug_info(message):
    """Helper function to print debug information."""
    print(f"[Camera Animator DEBUG] {message}")

def get_collection_objects(collection_name):
    """Retrieves all objects from a specified collection."""
    if collection_name not in bpy.data.collections:
        print_debug_info(f"Collection '{collection_name}' not found.")
        return []
    return list(bpy.data.collections[collection_name].objects)

def get_object_bounding_box_world(obj):
    """Calculates the world-space bounding box corners for a given object."""
    bpy.context.view_layer.update()
    return [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]

def get_combined_bounding_box_for_objects(objects):
    """Calculates the combined world-space bounding box for a list of objects."""
    if not objects:
        return None

    min_coords = Vector((float('inf'), float('inf'), float('inf')))
    max_coords = Vector((float('-inf'), float('-inf'), float('-inf')))

    for obj in objects:
        bbox_corners = get_object_bounding_box_world(obj)
        for corner in bbox_corners:
            min_coords.x = min(min_coords.x, corner.x)
            min_coords.y = min(min_coords.y, corner.y)
            min_coords.z = min(min_coords.z, corner.z)
            max_coords.x = max(max_coords.x, corner.x)
            max_coords.y = max(max_coords.y, corner.y)
            max_coords.z = max(max_coords.z, corner.z)

    return {
        'min': min_coords,
        'max': max_coords,
        'center': (min_coords + max_coords) / 2,
        'width': max_coords.x - min_coords.x,
        'depth': max_coords.y - min_coords.y,
        'height': max_coords.z - min_coords.z
    }

def calculate_tangent(curve_obj, position_factor):
    """Calculate tangent vector at a point on a curve."""
    curve = curve_obj.data
    if curve.splines:
        spline = curve.splines[0]
        if spline.type == 'BEZIER':
            points = spline.bezier_points
            n = len(points)
            if n == 0:
                return Vector((1, 0, 0))
                
            segment, t = math.modf(position_factor * (n - 1))
            segment = int(segment * (n - 1))
            t = t % 1.0
            
            if segment >= n - 1:
                segment = n - 2
                t = 1.0
                
            p0 = points[segment].co
            p1 = points[segment].handle_right
            p2 = points[segment+1].handle_left
            p3 = points[segment+1].co
            
            tangent = 3*(1-t)**2*(p1-p0) + 6*(1-t)*t*(p2-p1) + 3*t**2*(p3-p2)
            return tangent.normalized()
            
        elif spline.type == 'POLY':
            points = spline.points
            index = int(position_factor * (len(points) - 1))
            if index < len(points) - 1:
                return (points[index + 1].co - points[index].co).normalized()
    return Vector((1, 0, 0))

def get_model_scale_factors(model_collection_name):
    """Returns dictionary of model names and their scale factors."""
    scale_factors = {}
    if model_collection_name in bpy.data.collections:
        for obj in bpy.data.collections[model_collection_name].objects:
            if 'visual_scale_factor' in obj:
                scale_factors[obj.name] = obj['visual_scale_factor']
    return scale_factors

# --- Enhanced Camera Animation Function ---

def setup_camera_animation(
    curve_path_obj,
    animated_obj,
    anim_start_frame,
    anim_end_frame,
    number_of_data,
    x_axis_spread,
    target_collection,
    model_collection_name=None,
    min_camera_clearance=5.0,
    dynamic_intensity=1.0
):
    """
    Enhanced camera animation with:
    - Ultra-smooth dynamic pauses
    - Intelligent large model avoidance
    - Cinematic camera choreography
    - Perfectly timed movements
    """
    try:
        print_debug_info("STARTING CINEMATIC CAMERA ANIMATION SETUP")
        
        # --- Camera Setup ---
        camera_name = "Main_Visualization_Camera"
        if camera_name in bpy.data.objects:
            camera_obj = bpy.data.objects[camera_name]
            print_debug_info("Using existing camera")
        else:
            bpy.ops.object.camera_add()
            camera_obj = bpy.context.active_object
            camera_obj.name = camera_name
            bpy.context.scene.camera = camera_obj
            print_debug_info("Created new camera")

        # Link to target collection
        for coll in list(camera_obj.users_collection):
            coll.objects.unlink(camera_obj)
        target_collection.objects.link(camera_obj)

        # Clear existing animation data
        if camera_obj.animation_data:
            camera_obj.animation_data_clear()

        # Camera settings
        camera_obj.data.lens = 28.0  # Slightly wider than normal
        camera_obj.data.clip_end = 1000.0  # Ensure distant objects are visible

        # --- Scene Analysis ---
        all_models = []
        combined_bbox = None
        model_scales = {}
        
        if model_collection_name:
            all_models = get_collection_objects(model_collection_name)
            combined_bbox = get_combined_bounding_box_for_objects(all_models)
            model_scales = get_model_scale_factors(model_collection_name)

        # --- Initial Camera Positioning ---
        if combined_bbox:
            # Position camera lower, left, and further back
            initial_pos = Vector((
                combined_bbox['min'].x - min_camera_clearance * 3.5,  # Further left
                -30 * dynamic_intensity,  # Further back (increased from -25)
                combined_bbox['max'].z * 0.3  # Lower height (30% of max)
            ))
        else:
            initial_pos = Vector((-20, -30, 15))  # Default position

        camera_obj.location = initial_pos
        print_debug_info(f"Initial camera position: {initial_pos}")

        # --- Camera Constraints ---
        # Follow Path constraint
        follow_path = camera_obj.constraints.new(type='FOLLOW_PATH')
        follow_path.target = curve_path_obj
        follow_path.forward_axis = 'TRACK_NEGATIVE_Y'
        follow_path.up_axis = 'UP_Z'
        follow_path.use_fixed_location = True

        # Animate path follow with smooth easing
        follow_path.offset_factor = 0.0
        follow_path.keyframe_insert("offset_factor", frame=anim_start_frame)
        follow_path.offset_factor = 1.0
        follow_path.keyframe_insert("offset_factor", frame=anim_end_frame)

        # Track To constraint
        track_to = camera_obj.constraints.new(type='TRACK_TO')
        track_to.target = animated_obj
        track_to.track_axis = 'TRACK_NEGATIVE_Z'
        track_to.up_axis = 'UP_Y'

        # --- Cinematic Camera Positions ---
        # Base positions (x, y, z) relative to animated object
        cinematic_poses = [
            (0, -25, 5),      # Standard side view
            (4, -22, 4),      # Slightly right
            (-4, -22, 4),     # Slightly left 
            (0, -30, 6),      # Further back
            (7, -25, 3.5),    # Right side
            (-7, -25, 3.5),   # Left side
            (0, -18, 4.5),    # Closer view
            (5, -28, 5),      # Right and back
            (-5, -28, 5),     # Left and back
            (2, -20, 3.8),    # Slight right, medium
            (-2, -20, 3.8),   # Slight left, medium
            (0, -35, 7)       # Very far back
        ]

        # --- Animation Timing ---
        segment_length = (anim_end_frame - anim_start_frame) / max(1, (number_of_data - 1))
        move_duration = segment_length * 0.6  # 60% for movement
        hold_duration = segment_length * 0.4  # 40% for holds
        ease_in_out = 0.3  # 30% of move for easing

        # --- Keyframe Utilities ---
        def add_smooth_keyframe(obj, frame, interpolation='BEZIER', easing='EASE_IN_OUT'):
            obj.keyframe_insert("location", frame=frame)
            if obj.animation_data and obj.animation_data.action:
                for fcurve in obj.animation_data.action.fcurves:
                    if fcurve.data_path == "location":
                        for kf in fcurve.keyframe_points:
                            if kf.co[0] == frame:
                                kf.interpolation = interpolation
                                kf.easing = easing

        def get_safe_camera_position(base_pos, data_point_idx):
            """Adjust position to avoid large models."""
            adjusted_pos = Vector(base_pos)
            
            if not all_models or not model_scales:
                return adjusted_pos

            # Estimate data point position
            data_point_pos = Vector((
                x_axis_spread * data_point_idx,
                0,
                0  # Z will be from actual data
            ))

            for model in all_models:
                if model.name in model_scales:
                    scale_factor = model_scales[model.name]
                    if scale_factor > 1.2:  # Adjust for medium/large models
                        model_pos = model.location
                        distance = (data_point_pos - model_pos).length
                        
                        # If camera would be too close to a large model
                        if distance < (scale_factor * 3):
                            # Push camera further back in Y direction
                            back_factor = 1 + (scale_factor * 0.3)
                            adjusted_pos.y *= back_factor
                            print_debug_info(f"Adjusted camera back {back_factor:.1f}x for {model.name}")

            return adjusted_pos

        # --- Animation Sequence ---
        # Initial position
        add_smooth_keyframe(camera_obj, anim_start_frame)

        # Create camera path through data points
        for i in range(number_of_data):
            current_frame = anim_start_frame + (i * segment_length)
            pose_index = i % len(cinematic_poses)
            base_pose = cinematic_poses[pose_index]
            
            # Get safe adjusted position
            safe_pose = get_safe_camera_position(base_pose, i)
            
            # Add slight organic variation
            varied_pose = Vector((
                safe_pose.x * uniform(0.97, 1.03),
                safe_pose.y * uniform(0.95, 1.05),
                safe_pose.z * uniform(0.98, 1.02)
            ))

            # Calculate move timing
            move_start = current_frame - (move_duration * (1 - ease_in_out))
            move_end = current_frame + (move_duration * ease_in_out)
            hold_end = current_frame + hold_duration

            # Move to new position (with smooth easing)
            camera_obj.location = varied_pose
            add_smooth_keyframe(camera_obj, move_start)
            add_smooth_keyframe(camera_obj, move_end)
            
            # Hold position with subtle movement
            hold_variation = Vector((
                varied_pose.x * uniform(0.99, 1.01),
                varied_pose.y * uniform(0.98, 1.02),
                varied_pose.z * uniform(0.99, 1.01)
            ))
            camera_obj.location = hold_variation
            add_smooth_keyframe(camera_obj, hold_end)

        # Final position
        add_smooth_keyframe(camera_obj, anim_end_frame)

        print_debug_info("Cinematic camera animation setup complete")
        return True

    except Exception as e:
        print_debug_info(f"Error in cinematic camera setup: {e}")
        traceback.print_exc()
        return False

# --- Compatibility Wrapper ---

def generate_camera_animation(
    camera_mode: str,
    model_collection_name: str,
    graph_curve_object_name: str,
    graph_animated_object_name: str,
    animation_start_frame: int,
    animation_end_frame: int,
    min_camera_clearance: float,
    dynamic_movement_intensity: float,
    camera_dynamic_zoom_factor: float,
    camera_vertical_bob_amplitude: float,
    camera_horizontal_drift_amplitude: float,
    camera_dynamic_motion_frequency: float,
    camera_base_vertical_offset_factor: float,
    camera_base_horizontal_offset_factor: float
):
    """
    Wrapper function to maintain compatibility with existing pipeline.
    """
    # Get required objects
    curve_path_obj = bpy.data.objects.get(graph_curve_object_name)
    animated_obj = bpy.data.objects.get(graph_animated_object_name)
    
    if not curve_path_obj or not animated_obj:
        print_debug_info("Missing required objects for camera animation")
        return False
    
    # Calculate number of data points from curve
    number_of_data = 10  # Default fallback
    if curve_path_obj.data.splines:
        number_of_data = len(curve_path_obj.data.splines[0].bezier_points)
    
    # Get target collection (create if needed)
    target_collection = bpy.data.collections.get("Camera_Animations")
    if not target_collection:
        target_collection = bpy.data.collections.new("Camera_Animations")
        bpy.context.scene.collection.children.link(target_collection)
    
    return setup_camera_animation(
        curve_path_obj=curve_path_obj,
        animated_obj=animated_obj,
        anim_start_frame=animation_start_frame,
        anim_end_frame=animation_end_frame,
        number_of_data=number_of_data,
        x_axis_spread=min_camera_clearance,
        target_collection=target_collection,
        model_collection_name=model_collection_name,
        min_camera_clearance=min_camera_clearance,
        dynamic_intensity=dynamic_movement_intensity
    )

def register():
    pass

def unregister():
    pass

if __name__ == "__main__":
    print("=" * 50)
    print("CINEMATIC CAMERA ANIMATOR STANDALONE TEST")
    print("=" * 50)
    
    # Example test call
    generate_camera_animation(
        camera_mode='SIDEWAYS_TRACKING_VIEW',
        model_collection_name="Viz_Models",
        graph_curve_object_name="Graph_Curve",
        graph_animated_object_name="Animated_Graph_Object",
        animation_start_frame=1,
        animation_end_frame=250,
        min_camera_clearance=5.0,
        dynamic_movement_intensity=1.0,
        camera_dynamic_zoom_factor=5.0,
        camera_vertical_bob_amplitude=1.0,
        camera_horizontal_drift_amplitude=2.0,
        camera_dynamic_motion_frequency=20.0,
        camera_base_vertical_offset_factor=0.3,
        camera_base_horizontal_offset_factor=1.8
    )