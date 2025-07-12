import bpy
import math
import csv
import os
import traceback

# Global Blender version for compatibility checks
MAJOR_VERSION, MINOR_VERSION, SUB_VERSION = bpy.app.version

###########################################################################
###########################################################################
#
# --- USER CONFIGURATION: Graph Animation Settings ---
# These are now defaults, as the Init script will provide actual values.


CSV_FILE_PATH = r"C:\Data\Database.csv"  # <--- VERIFY THIS PATH CAREFULLY
# Changed to column names (strings) - these are defaults
DATA_COLUMN_NAME = "Value"
MONTH_COLUMN_NAME = "Month"
DATA_UNIT_SYMBOL = ""  # Changed from CURRENCY_SYMBOL to DATA_UNIT_SYMBOL, default to empty string

GRAPH_ANIM_START_FRAME = 2
GRAPH_ANIM_LENGTH_DATA = 100  # Adjusted: Made twice as slow (100 * 2 = 200)
GRAPH_START_POSITION = 0  # This will be largely overridden by stats_model_positions
GRAPH_X_AXIS_SPREAD = 2  # This will be largely overridden by stats_model_positions

# Custom Animated Object Settings for Graph
ANIMATED_OBJECT_TYPE = "CYLINDER"  # Choose 'CUBE', 'CONE', or 'CYLINDER'
ANIMATED_OBJECT_NAME = "Animated_Graph_Object"
ANIMATED_OBJECT_SCALE = 0.1  # Initial scale for the custom object

# NEW CONFIGURATION: Control rebuild behavior specific to graph animator
REBUILD_GRAPH_ON_RUN = False


###########################################################################
###########################################################################


# --- Global variables for graph specific context ---
_graph_context = {}


# --- Helper Functions ---

def print_debug_info(message):
    """Helper function to print debug information."""
    print(f"[Graph Animator DEBUG] {message}")


def clear_graph_elements():
    """
    Clears all objects and collections previously created by this script.
    """
    print_debug_info("Cleaning up existing graph elements...")

    # Deselect all objects first
    bpy.ops.object.select_all(action='DESELECT')

    graph_collection_name = "Graph_Elements"
    if graph_collection_name in bpy.data.collections:
        graph_collection = bpy.data.collections[graph_collection_name]
        for obj in list(graph_collection.objects):  # Iterate over a copy of the list
            bpy.data.objects.remove(obj, do_unlink=True)
        # Remove the collection itself if it's empty
        if not graph_collection.objects:
            bpy.data.collections.remove(graph_collection)
        print_debug_info(f"Removed collection and its objects: {graph_collection.name}")

    # Clean up any remaining materials
    mats_to_remove = []
    for mat in bpy.data.materials:
        if mat.name.startswith("graph_material_"):
            is_used = False
            # Check if material is still used by any mesh
            for mesh in bpy.data.meshes:
                if mat in mesh.materials:
                    is_used = True
                    break
            if not is_used:
                mats_to_remove.append(mat)
    for mat in mats_to_remove:
        bpy.data.materials.remove(mat)
        print_debug_info(f"Removed unused material: {mat.name}")

    # Clean up any remaining curves
    curves_to_remove = []
    for curve in bpy.data.curves:
        if curve.name.startswith("data_curve") or curve.name.startswith("Graph_Curve"):
            if not curve.users:  # Check if it has no users (objects using this curve data)
                curves_to_remove.append(curve)
    for curve in curves_to_remove:
        bpy.data.curves.remove(curve)
        print_debug_info(f"Removed unused curve data: {curve.name}")

    print_debug_info("Graph elements cleanup complete.")


def create_graph_curve_path(graph_data_values, graph_point_positions, graph_anim_start_frame, graph_anim_length_data, graph_collection):
    """
    Creates a Bezier curve path based on the provided data points.
    The curve will be animated using a 'Build' modifier.
    """
    print_debug_info("Creating graph curve path...")

    # Create a new curve datablock
    curve_data = bpy.data.curves.new(name="data_curve", type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = 2

    # Create a new spline in the curve
    spline = curve_data.splines.new(type='BEZIER')

    # Add points based on graph_point_positions
    # We need at least 2 points to create a spline
    if not graph_point_positions or len(graph_point_positions) < 2:
        print_debug_info("Not enough points to create a curve path. Minimum 2 points required.")
        return None

    # Resize points array to match the number of positions
    spline.bezier_points.add(len(graph_point_positions) - 1)

    for i, pos_data in enumerate(graph_point_positions):
        point = spline.bezier_points[i]
        x, z = pos_data['x_pos'], pos_data['base_z']
        point.co = (x, 0, z)  # X, 0 for Y (flat on XZ plane), Z
        point.handle_left_type = 'AUTO'
        point.handle_right_type = 'AUTO'

    # Create a new object for the curve
    curve_path_obj = bpy.data.objects.new("Graph_Curve", curve_data)
    graph_collection.objects.link(curve_path_obj)

    # Add a Build modifier for animation
    build_modifier = curve_path_obj.modifiers.new(name="Build", type='BUILD')
    # build_modifier.use_random = False # Removed as per user debugging and traceback

    
    
    build_modifier.frame_start = graph_anim_start_frame
    build_modifier.frame_duration = (len(graph_data_values) * graph_anim_length_data)

    print_debug_info(f"Created curve object: {curve_path_obj.name} with build modifier ending at frame {build_modifier.frame_start + build_modifier.frame_duration}")
    return curve_path_obj


def create_animated_object(animated_object_type, animated_object_name, animated_object_scale, graph_collection):
    """
    Creates a simple mesh object (cube, cone, or cylinder) to animate along the graph path.
    """
    print_debug_info(f"Creating animated object: {animated_object_name} of type {animated_object_type}...")
    bpy.ops.object.select_all(action='DESELECT') # Deselect all

    mesh = None
    if animated_object_type.upper() == 'CUBE':
        bpy.ops.mesh.primitive_cube_add(size=animated_object_scale, enter_editmode=False, align='WORLD', location=(0, 0, 0))
        mesh = bpy.context.active_object
    elif animated_object_type.upper() == 'CONE':
        bpy.ops.mesh.primitive_cone_add(radius1=animated_object_scale, depth=animated_object_scale * 2, enter_editmode=False, align='WORLD', location=(0, 0, 0))
        mesh = bpy.context.active_object
    elif animated_object_type.upper() == 'CYLINDER':
        bpy.ops.mesh.primitive_cylinder_add(radius=animated_object_scale, depth=animated_object_scale * 2, enter_editmode=False, align='WORLD', location=(0, 0, 0))
        mesh = bpy.context.active_object
    else:
        print_debug_info(f"Unsupported animated object type: {animated_object_type}. Defaulting to CYLINDER.")
        bpy.ops.mesh.primitive_cylinder_add(radius=animated_object_scale, depth=animated_object_scale * 2, enter_editmode=False, align='WORLD', location=(0, 0, 0))
        mesh = bpy.context.active_object

    if mesh:
        mesh.name = animated_object_name
        graph_collection.objects.link(mesh)
        print_debug_info(f"Created animated object: {mesh.name}")
        return mesh
    return None


def setup_path_animation(animated_obj, curve_path_obj, graph_anim_start_frame, anim_duration):
    """
    Sets up the animation of an object along a curve path.
    """
    print_debug_info("Setting up path animation...")
    if not animated_obj or not curve_path_obj:
        print_debug_info("Animated object or curve path missing. Skipping path animation setup.")
        return

    # Add Follow Path constraint
    constraint = animated_obj.constraints.new(type='FOLLOW_PATH')
    constraint.target = curve_path_obj
    constraint.use_curve_follow = True

    constraint.forward_axis = 'FORWARD_Y'  # Assumes object is pointing along Y axis, adjust if needed
    constraint.up_axis = 'UP_Z'

    # Ensure the curve data has path animation enabled
    curve_path_obj.data.use_path = True
    curve_path_obj.data.path_duration = anim_duration  # Total frames for the path animation
    print_debug_info(f"Path duration set to {anim_duration} frames.")

    # Keyframe the evaluation time of the curve
    # The 'eval_time' goes from 0 to path_duration
    curve_path_obj.data.eval_time = 0
    curve_path_obj.data.keyframe_insert(data_path="eval_time", frame=graph_anim_start_frame)

    curve_path_obj.data.eval_time = anim_duration
    curve_path_obj.data.keyframe_insert(data_path="eval_time", frame=graph_anim_start_frame + anim_duration)

    print_debug_info(f"Animated object '{animated_obj.name}' set to follow '{curve_path_obj.name}'.")
    print_debug_info(f"Path animation keyframed from frame {graph_anim_start_frame} to {graph_anim_start_frame + anim_duration}.")


def create_data_labels(graph_data_values, graph_category_labels, data_unit_symbol, graph_point_positions, graph_collection):
    """
    Creates text objects for data values and category labels.
    Text size scales with model height, and text faces the camera by copying camera's rotation.
    """
    print_debug_info("Creating data labels...")
    if not graph_data_values or not graph_point_positions:
        print_debug_info("No data or positions to create labels from.")
        return []

    labels = []
    # Create materials for labels
    if "graph_material_text" not in bpy.data.materials:
        text_mat = bpy.data.materials.new(name="graph_material_text")
        text_mat.diffuse_color = (1.0, 1.0, 1.0, 1.0) # White
        text_mat.use_nodes = True
        bsdf = text_mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0) # White
        print_debug_info("Created material: graph_material_text")
    else:
        text_mat = bpy.data.materials["graph_material_text"]

    # Get the main camera object (assuming it exists and is named 'Camera')
    camera_obj = bpy.data.objects.get('Camera')
    if not camera_obj:
        print_debug_info("Warning: 'Camera' object not found. Text will not be tracked to camera.")

    # Define min/max model height for scaling reference (from Stats_Generator's MIN/MAX_VISUAL_SCALE)
    # These values must match those in Stats_Generator.py for consistent scaling.
    min_model_height_ref = 5.0
    max_model_height_ref = 300.0

    # Define min/max font size for clamping the calculated size
    min_font_size_clamp = 0.5
    max_font_size_clamp = 50.0 

    # Add a small constant offset to ensure text is clearly outside the model
    text_horizontal_clearance = 0.5 # A small gap from the model's edge

    # Y position offset (not aligned at y=0)
    text_y_position = -1.0 # Increased negative offset in Y to prevent overlap

    for i, (value, category, pos_data) in enumerate(zip(graph_data_values, graph_category_labels, graph_point_positions)):
        x_model_center = pos_data['x_pos']
        z_model_top = pos_data['base_z']
        # Retrieve the visual_scale_factor from pos_data, defaulting to 1.0 if not present
        visual_scale_factor = pos_data.get('visual_scale_factor', 1.0) 

        print_debug_info(f"Creating labels for point {i}: x={x_model_center}, z={z_model_top}, scale={visual_scale_factor}, value={value}, category={category}")

        # Calculate dynamic font size based on model height
        model_height = z_model_top # Use base_z as model_height for scaling font size
        
        # Avoid division by zero if min and max model heights are the same
        if max_model_height_ref - min_model_height_ref == 0:
            scaling_ratio = 0.5 # Default to middle if range is zero (e.g., all models same size)
        else:
            # Normalize model_height to a 0-1 range based on min/max reference heights
            scaling_ratio = (model_height - min_model_height_ref) / (max_model_height_ref - min_model_height_ref)
        
        # Calculate font size using linear interpolation and clamp
        calculated_font_size = min_font_size_clamp + scaling_ratio * (max_font_size_clamp - min_font_size_clamp)
        calculated_font_size = max(min_font_size_clamp, min(max_font_size_clamp, calculated_font_size)) # Final clamping

        # Adjusted vertical positions based on font size to place them slightly above the bar tip
        value_z_offset = calculated_font_size * 1.0 
        category_z_offset = calculated_font_size * 0.6 

        # Calculate the X position for the text: model center - half its width - clearance
        # Assuming TARGET_BASE_DIMENSION (from Stats_Generator) defines the base width, usually 1.0
        # The model's actual half-width in X (or overall horizontal footprint) will be 0.5 * visual_scale_factor
        model_half_width = 0.5 * visual_scale_factor 
        text_x_position = x_model_center - model_half_width - text_horizontal_clearance


        # Value label
        value_text = f"{value}{data_unit_symbol}"
        # Position text to the left of the model with Y-offset
        bpy.ops.object.text_add(enter_editmode=False, align='WORLD', location=(text_x_position, text_y_position, z_model_top + value_z_offset))
        value_obj = bpy.context.active_object
        value_obj.data.body = value_text
        value_obj.data.align_x = 'RIGHT' # Text's right edge is at text_x_position, extending left
        value_obj.name = f"Data_Value_Label_{i}"
        value_obj.data.extrude = 0.01 # Make text 3D
        value_obj.data.size = calculated_font_size # Apply dynamic font size
        if text_mat:
            if len(value_obj.data.materials) == 0:
                value_obj.data.materials.append(text_mat)
            else:
                value_obj.data.materials[0] = text_mat
        graph_collection.objects.link(value_obj)

        # Ensure all existing TRACK_TO constraints are removed
        for constraint in list(value_obj.constraints):
            if constraint.type == 'TRACK_TO':
                value_obj.constraints.remove(constraint)

        # Add Copy Rotation constraint to make text rotate exactly with the camera
        if camera_obj:
            copy_rot_constraint = value_obj.constraints.new(type='COPY_ROTATION')
            copy_rot_constraint.target = camera_obj
            copy_rot_constraint.owner_space = 'WORLD' # Copy world rotation
            copy_rot_constraint.target_space = 'WORLD' # Copy world rotation


        labels.append(value_obj)

        # Category label (optional, if category data is meaningful)
        if category:
            # Position text to the left of the model with Y-offset
            bpy.ops.object.text_add(enter_editmode=False, align='WORLD', location=(text_x_position, text_y_position, z_model_top + category_z_offset))
            category_obj = bpy.context.active_object
            category_obj.data.body = str(category)
            category_obj.data.align_x = 'RIGHT' # Text's right edge is at text_x_position, extending left
            category_obj.name = f"Category_Label_{i}"
            category_obj.data.extrude = 0.01 # Make text 3D
            category_obj.data.size = calculated_font_size * 0.8 # Category a bit smaller than value
            if text_mat:
                if len(category_obj.data.materials) == 0:
                    category_obj.data.materials.append(text_mat)
                else:
                    category_obj.data.materials[0] = text_mat
            graph_collection.objects.link(category_obj)

            # Ensure all existing TRACK_TO constraints are removed
            for constraint in list(category_obj.constraints):
                if constraint.type == 'TRACK_TO':
                    category_obj.constraints.remove(constraint)

            # Add Copy Rotation constraint to make text rotate exactly with the camera
            if camera_obj:
                copy_rot_constraint = category_obj.constraints.new(type='COPY_ROTATION')
                copy_rot_constraint.target = camera_obj
                copy_rot_constraint.owner_space = 'WORLD'
                copy_rot_constraint.target_space = 'WORLD'

            labels.append(category_obj)

    print_debug_info(f"Created {len(labels)} data and category labels.")
    return labels


def create_vertical_lines(graph_point_positions, min_visual_scale, graph_collection):
    """
    Creates vertical lines from the base of the scene to the data points.
    """
    print_debug_info("Creating vertical lines...")
    if not graph_point_positions:
        print_debug_info("No data to create vertical lines from.")
        return []

    lines = []
    # Create materials for lines
    if "graph_material_data_points" not in bpy.data.materials:
        line_mat = bpy.data.materials.new(name="graph_material_data_points")
        line_mat.diffuse_color = (0.05, 0.4, 0.8, 1.0) # Blueish
        line_mat.use_nodes = True
        bsdf = line_mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.05, 0.4, 0.8, 1.0) # Blueish
        print_debug_info("Created material: graph_material_data_points")
    else:
        line_mat = bpy.data.materials["graph_material_data_points"]


    for i, pos_data in enumerate(graph_point_positions):
        x, z = pos_data['x_pos'], pos_data['base_z']
        print_debug_info(f"Creating vertical line for point {i}: x={x}, z={z}")

        # Ensure z (depth) is positive and not too small for cylinder creation
        # Add a very small epsilon if z is effectively zero or negative to prevent issues with primitive creation.
        effective_z_depth = max(0.001, z)
        if z < 0:
            print_debug_info(f"Warning: Negative Z value ({z}) encountered for vertical line. Using {effective_z_depth} as depth.")

        # Create a cylinder for the line to ensure it renders with thickness
        bpy.ops.mesh.primitive_cylinder_add(
            radius=min_visual_scale * 0.05, # Thin cylinder based on min_visual_scale
            depth=effective_z_depth, # Use the checked depth
            enter_editmode=False,
            align='WORLD',
            location=(x, 0, effective_z_depth / 2) # Position at midpoint using effective_z_depth
        )
        cylinder_obj = bpy.context.active_object
        cylinder_obj.name = f"Data_Line_Cylinder_{i}"
        graph_collection.objects.link(cylinder_obj)

        if line_mat:
            if len(cylinder_obj.data.materials) == 0:
                cylinder_obj.data.materials.append(line_mat)
            else:
                cylinder_obj.data.materials[0] = line_mat
        lines.append(cylinder_obj)

    print_debug_info(f"Created {len(lines)} vertical lines.")
    return lines


class GraphAnimatorOperator(bpy.types.Operator):
    """Blender Operator to generate graph animation."""
    bl_idname = "object.generate_graph_animation"
    bl_label = "Generate Graph Animation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            # Parameters will be passed programmatically, but define them for operator registration
            # These will be overridden by the call from Init_Blender_Animation.py
            graph_data_values = [10, 20, 15, 25, 30]
            graph_category_labels = ["Jan", "Feb", "Mar", "Apr", "May"]
            data_unit_symbol = DATA_UNIT_SYMBOL
            graph_anim_start_frame = GRAPH_ANIM_START_FRAME
            graph_anim_length_data = GRAPH_ANIM_LENGTH_DATA
            graph_start_position = GRAPH_START_POSITION
            graph_x_axis_spread = GRAPH_X_AXIS_SPREAD
            animated_object_type = ANIMATED_OBJECT_TYPE
            animated_object_name = ANIMATED_OBJECT_NAME
            animated_object_scale = ANIMATED_OBJECT_SCALE
            rebuild_graph_on_run = REBUILD_GRAPH_ON_RUN
            graph_point_positions = None # Default, will be overridden by Init script

            # Call the main generation function
            generate_graph_animation(
                graph_data_values=graph_data_values,
                graph_category_labels=graph_category_labels,
                data_unit_symbol=data_unit_symbol,
                graph_anim_start_frame=graph_anim_start_frame,
                graph_anim_length_data=graph_anim_length_data,
                graph_start_position=graph_start_position,
                graph_x_axis_spread=graph_x_axis_spread,
                animated_object_type=animated_object_type,
                animated_object_name=animated_object_name,
                animated_object_scale=animated_object_scale,
                rebuild_graph_on_run=rebuild_graph_on_run,
                graph_point_positions=graph_point_positions
            )
            self.report({'INFO'}, "Graph animation generated successfully.")
            return {'FINISHED'}
        except Exception as e:
            print(f"Error in GraphAnimatorOperator: {e}")
            traceback.print_exc()
            self.report({'ERROR'}, f"Graph animation failed: {e}")
            return {'CANCELLED'}


def generate_graph_animation(graph_data_values, graph_category_labels, data_unit_symbol,
                             graph_anim_start_frame, graph_anim_length_data,
                             graph_start_position, graph_x_axis_spread,
                             animated_object_type, animated_object_name,
                             animated_object_scale, rebuild_graph_on_run,
                             graph_point_positions=None):
    """
    Main function to orchestrate the graph animation generation.
    Takes data directly from Init_Blender_Animation.
    """
    print("=" * 50)
    print("STARTING BLENDER GRAPH ANIMATOR SCRIPT (Programmatic Call)")
    print("=" * 50)

    if rebuild_graph_on_run:
        clear_graph_elements()

    # Ensure Graph_Elements collection exists
    if "Graph_Elements" not in bpy.data.collections:
        graph_collection = bpy.data.collections.new("Graph_Elements")
        bpy.context.scene.collection.children.link(graph_collection)
        print_debug_info(f"Created collection: {graph_collection.name}")
    else:
        graph_collection = bpy.data.collections["Graph_Elements"]
        print_debug_info(f"Using collection: {graph_collection.name}")

    if not graph_data_values:
        print("No graph data provided. Skipping graph animation.")
        return None

    number_of_data = len(graph_data_values)
    anim_duration = number_of_data * graph_anim_length_data

    curve_path_obj = None
    animated_obj = None
    all_labels = []
    all_lines = []

    # If graph_point_positions are provided (from Stats_Generator), use them
    # Otherwise, calculate default positions based on graph_start_position and graph_x_axis_spread
    if graph_point_positions:
        print_debug_info("Using graph_point_positions provided by Stats_Generator.")
        # Need to determine a reasonable 'min_visual_scale' for vertical lines from this context
        # A rough estimate for line thickness if not passed in directly.
        # This value should ideally come from Stats_Generator's min_visual_scale
        # For now, let's assume a small default if not explicitly available.
        temp_min_visual_scale = 0.5 
        
        # Create materials for graph elements
        print_debug_info("Checking/creating graph materials...")
        if "graph_material_data_points" not in bpy.data.materials:
            line_mat = bpy.data.materials.new(name="graph_material_data_points")
            line_mat.diffuse_color = (0.05, 0.4, 0.8, 1.0) # Blueish
            line_mat.use_nodes = True
            bsdf = line_mat.node_tree.nodes["Principled BSDF"]
            bsdf.inputs["Base Color"].default_value = (0.05, 0.4, 0.8, 1.0) # Blueish
            print_debug_info("Created material: graph_material_data_points")
        else:
            line_mat = bpy.data.materials["graph_material_data_points"]

        if "graph_material_text" not in bpy.data.materials:
            text_mat = bpy.data.materials.new(name="graph_material_text")
            text_mat.diffuse_color = (1.0, 1.0, 1.0, 1.0) # White
            text_mat.use_nodes = True
            bsdf = text_mat.node_tree.nodes["Principled BSDF"]
            bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0) # White
            print_debug_info("Created material: graph_material_text")
        else:
            text_mat = bpy.data.materials["graph_material_text"]

        print_debug_info("Calling create_vertical_lines...")
        all_lines = create_vertical_lines(graph_point_positions, temp_min_visual_scale, graph_collection)
        print_debug_info("Finished create_vertical_lines.")

        print_debug_info("Calling create_data_labels...")
        all_labels = create_data_labels(graph_data_values, graph_category_labels, data_unit_symbol, graph_point_positions, graph_collection)
        print_debug_info("Finished create_data_labels.")

        print_debug_info("Calling create_graph_curve_path...")
        curve_path_obj = create_graph_curve_path(graph_data_values, graph_point_positions, graph_anim_start_frame, graph_anim_length_data, graph_collection)
        print_debug_info("Finished create_graph_curve_path.")

        if curve_path_obj:
            print_debug_info("Calling create_animated_object...")
            animated_obj = create_animated_object(animated_object_type, animated_object_name, animated_object_scale, graph_collection)
            print_debug_info("Finished create_animated_object.")
            if animated_obj:
                print_debug_info("Calling setup_path_animation...")
                setup_path_animation(animated_obj, curve_path_obj, graph_anim_start_frame, anim_duration)
                print_debug_info("Finished setup_path_animation.")

    else:
        print_debug_info("No graph_point_positions provided. Calculating default positions (Fallback).")
        # Fallback to older behavior if graph_point_positions is not provided
        # This path should ideally not be taken if Init_Blender_Animation is working correctly
        current_x = graph_start_position
        # Ensure graph_point_positions is a mutable list for appending in this fallback
        graph_point_positions = []
        for i, value in enumerate(graph_data_values):
            x = current_x
            z = value * 0.1 # Simple scaling for graph points if no stats data
            graph_point_positions.append({'x_pos': x, 'base_z': z, 'visual_scale_factor': 1.0}) # Append to an empty list, add default scale
            current_x += graph_x_axis_spread

        curve_path_obj = create_graph_curve_path(graph_data_values, graph_point_positions, graph_anim_start_frame, graph_anim_length_data, graph_collection)
        if curve_path_obj:
            animated_obj = create_animated_object(animated_object_type, animated_object_name, animated_object_scale, graph_collection)
            if animated_obj:
                setup_path_animation(animated_obj, curve_path_obj, graph_anim_start_frame, anim_duration)
        all_labels = create_data_labels(graph_data_values, graph_category_labels, data_unit_symbol, graph_point_positions, graph_collection)
        all_lines = create_vertical_lines(graph_point_positions, 0.5, graph_collection) # Default thickness

    # Set Blender's scene end frame if animation goes beyond current end frame
    anim_end_frame = graph_anim_start_frame + anim_duration + graph_anim_length_data # Add some buffer frames
    if bpy.context.scene.frame_end < anim_end_frame:
        bpy.context.scene.frame_end = anim_end_frame

    print_debug_info(f"Graph animation generated. Animation set from frame {bpy.context.scene.frame_start} to {bpy.context.scene.frame_end}.")
    print("Please check the 'Graph_Elements' collection in your Blender Outliner.")

    # Return key information for the Init script
    return {
        "graph_collection_name": graph_collection.name,
        "curve_object_name": curve_path_obj.name if curve_path_obj else None,
        "animated_object_name": animated_obj.name if animated_obj else None,
        "animation_start_frame": graph_anim_start_frame,
        "animation_end_frame": anim_end_frame,
        "number_of_data_points": number_of_data
    }


def register():
    bpy.utils.register_class(GraphAnimatorOperator)


def unregister():
    # Only unregister if it's actually registered to avoid runtime errors
    try:
        bpy.utils.unregister_class(GraphAnimatorOperator)
    except RuntimeError:
        pass # Ignore if not registered


def main():
    """
    Main function to orchestrate the graph generation.
    Registers and runs the operator.
    """
    print("=" * 50)
    print("STARTING BLENDER GRAPH ANIMATOR SCRIPT (Direct Run)")
    print("=" * 50)

    # Ensure the operator is registered before calling it
    try:
        bpy.utils.register_class(GraphAnimatorOperator)
    except ValueError:
        # Already registered, unregister and re-register to ensure latest version
        bpy.utils.unregister_class(GraphAnimatorOperator)
        bpy.utils.register_class(GraphAnimatorOperator)

    # Example usage for direct running (these values would normally come from Init_Blender_Animation)
    example_data_values = [10, 50, 20, 80, 30, 90, 40, 70, 50, 60]
    example_category_labels = [f"Item {i+1}" for i in range(len(example_data_values))]
    example_graph_point_positions = [{'x_pos': float(i*5), 'base_z': float(v), 'visual_scale_factor': 1.0} for i,v in enumerate(example_data_values)] # Added default scale


    # Run the operator
    bpy.ops.object.generate_graph_animation(
        # The following parameters are for operator call.
        # They will be overridden if called programmatically by Init_Blender_Animation.
        # For direct run, these provide default values.
    )

    print("BLENDER GRAPH ANIMATOR SCRIPT FINISHED (Direct Run)")
    print("=" * 50)


if __name__ == "__main__":
    # This block allows running the script directly in Blender's text editor for testing
    # Without this, it would only run when called as part of a larger addon/script system.
    main()