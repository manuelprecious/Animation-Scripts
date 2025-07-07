import bpy
import math
import csv
import os
import traceback

context = bpy.context
scene = bpy.context.scene # Use bpy.context.scene for consistency

# Global Blender version for compatibility checks
MAJOR_VERSION, MINOR_VERSION, SUB_VERSION = bpy.app.version

###########################################################################
###########################################################################
#
# CHANGE THE FOLLOWING INPUT AS PER YOUR CSV FILE AND PREFERENCES
# BE CAREFUL - ANY WRONG INPUT WILL RAISE AN ERROR.

CSV_FILE_PATH = r"C:\Data\Database.csv" # <--- VERIFY THIS PATH CAREFULLY
DATA_COLUMN = 3 # 1-indexed column number for numerical data
MONTH_COLUMN = 2 # 1-indexed column number for category/month labels
CURRENCY_SYMBOL = "$"

# Animation Settings
ANIM_START_FRAME = 2
ANIM_LENGTH_DATA = 100 # Adjusted: Made twice as slow (100 * 2 = 200)
GRAPH_START_POSITION = 0
X_AXIS_SPREAD = 10 # Increased distance between points for wider bases

# Custom Animated Object Settings
# Choose 'CUBE', 'CONE', or 'CYLINDER' for the default placeholder object
ANIMATED_OBJECT_TYPE = 'CYLINDER' 
ANIMATED_OBJECT_NAME = "Animated_Graph_Object"
ANIMATED_OBJECT_SCALE = 0.5 # Initial scale for the custom object

###########################################################################
###########################################################################

def read_csv_data(csv_file_path, data_column, month_column):
    """
    Reads numerical data and month labels from a specified CSV file.

    Args:
        csv_file_path (str): The full path to the CSV file.
        data_column (int): 1-indexed column number for numerical data.
        month_column (int): 1-indexed column number for month/category labels.

    Returns:
        tuple: A tuple containing (data_list, month_list, number_of_data).
               Returns empty lists and 0 if an error occurs or no valid data.
    """
    data_list = []
    month_list = []
    number_of_data = 0

    if not os.path.exists(csv_file_path):
        print(f"Error: CSV file NOT found at specified path: {csv_file_path}")
        print("Please ensure the 'csv_file_path' variable in the script is correct.")
        return [], [], 0

    try:
        with open(csv_file_path, 'r', newline='') as file:
            csvreader = csv.reader(file)
            header = next(csvreader) # Read header row

            # Basic validation for column indices
            if not (1 <= data_column <= len(header)):
                print(f"Error: data_column ({data_column}) is out of bounds. Header has {len(header)} columns.")
                return [], [], 0
            if not (1 <= month_column <= len(header)):
                print(f"Error: month_column ({month_column}) is out of bounds. Header has {len(header)} columns.")
                return [], [], 0

            print(f"Reading CSV from: {csv_file_path}")
            print(f"Header: {header}")
            print(f"Using data from column '{header[data_column-1]}' (index {data_column-1})")
            print(f"Using month from column '{header[month_column-1]}' (index {month_column-1})")

            for row_idx, row in enumerate(csvreader):
                if len(row) >= max(data_column, month_column):
                    try:
                        data_value = float(row[data_column-1])
                        data_list.append(data_value)
                        month_list.append(str(row[month_column-1]))
                    except ValueError:
                        print(f"Warning: Non-numeric data found in data_column at row {row_idx+2}. Skipping row.")
                    except IndexError:
                        print(f"Warning: Row {row_idx+2} has fewer columns than expected. Skipping row.")
                else:
                    print(f"Warning: Row {row_idx+2} has too few columns. Skipping row.")

        number_of_data = len(month_list)
        print(f"Successfully read {number_of_data} data points from CSV.")
        return data_list, month_list, number_of_data

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        print("Please ensure the 'csv_file_path' is correct and the CSV format is valid.")
        traceback.print_exc()
        return [], [], 0

def normalize_and_display_data(data_list):
    """
    Normalizes the input data list for display purposes in Blender.

    Args:
        data_list (list): A list of numerical data points.

    Returns:
        list: A list of normalized data points ready for display.
    """
    if not data_list:
        return []

    data_height_mean = sum(data_list) / len(data_list) if len(data_list) > 0 else 1.0
    
    normalized_data = []
    if data_height_mean == 0:
        normalized_data = [0] * len(data_list)
    else:
        for data in data_list:
            normalized_data.append(data * 10 / data_height_mean)

    data_height_min = min(normalized_data) if normalized_data else 0

    display_data = []
    if (data_height_min < 0): # Only adjust if there are negative values
        offset = abs(data_height_min)
        for data in normalized_data:
            display_data.append(data + offset)
    else:
        display_data = normalized_data[:] # Create a copy

    return display_data

def setup_materials():
    """
    Creates and configures all necessary materials for the graph.

    Returns:
        tuple: A tuple containing (material_1, material_2, material_3, material_4).
    """
    materials = {}

    # Material 1 (Curve and Sphere/Animated Object)
    material_1 = bpy.data.materials.new(name = "anim_material_1")
    material_1.use_nodes = True
    nodes = material_1.node_tree.nodes
    links = material_1.node_tree.links
    nodes.clear() # Clear existing nodes
    output = nodes.new(type='ShaderNodeOutputMaterial')
    shader = nodes.new(type='ShaderNodeEmission')
    shader.inputs['Color'].default_value = (1.0, 0.3, 0.0, 1) # Orange
    shader.inputs['Strength'].default_value = 1.5
    links.new(shader.outputs[0], output.inputs[0])
    materials['material_1'] = material_1

    # Material 2 (Text)
    material_2 = bpy.data.materials.new(name = "anim_material_2")
    material_2.use_nodes = True
    nodes = material_2.node_tree.nodes
    links = material_2.node_tree.links
    nodes.clear()
    output = nodes.new(type='ShaderNodeOutputMaterial')
    shader = nodes.new(type='ShaderNodeEmission')
    shader.inputs['Strength'].default_value = 3.0 # Brighter white
    links.new(shader.outputs[0], output.inputs[0])
    materials['material_2'] = material_2

    # Material 3 (X-axis) - No longer directly used for axis, but kept in tuple for consistency
    material_3 = bpy.data.materials.new(name = "anim_material_3")
    material_3.use_nodes = True
    nodes = material_3.node_tree.nodes
    links = material_3.node_tree.links
    nodes.clear()
    output = nodes.new(type='ShaderNodeOutputMaterial')
    shader = nodes.new(type='ShaderNodeBsdfPrincipled')
    shader.inputs[0].default_value = (1.0, 0.05, 0.135, 1) # Reddish
    links.new(shader.outputs[0], output.inputs[0])
    materials['material_3'] = material_3

    # Material 4 (Z-axis) - No longer directly used for axis, but kept in tuple for consistency
    material_4 = bpy.data.materials.new(name = "anim_material_4")
    material_4.use_nodes = True
    nodes = material_4.node_tree.nodes
    links = material_4.node_tree.links
    nodes.clear()
    output = nodes.new(type='ShaderNodeOutputMaterial')
    shader = nodes.new(type='ShaderNodeBsdfPrincipled')
    shader.inputs[0].default_value = (0.0, 0.24, 0.6, 1) # Blueish
    links.new(shader.outputs[0], output.inputs[0])
    materials['material_4'] = material_4

    return (materials['material_1'], materials['material_2'], 
            materials['material_3'], materials['material_4'])

def create_curve_and_animated_object(display_data, graph_start_position, x_axis_spread, anim_start_frame, anim_end_frame, material_1, object_type, object_name, object_scale):
    """
    Creates the 3D curve based on data and a custom object that follows it.
    The curve's animation (trimming) is handled by Geometry Nodes.

    Args:
        display_data (list): Normalized data points for curve height.
        graph_start_position (float): Starting X-coordinate for the graph.
        x_axis_spread (float): Distance between data points on the X-axis.
        anim_start_frame (int): The frame at which the animation starts.
        anim_end_frame (int): The frame at which the animation ends.
        material_1 (bpy.types.Material): Material for the curve and animated object.
        object_type (str): Type of primitive object to create ('CUBE', 'CONE', 'CYLINDER').
        object_name (str): Name for the animated object.
        object_scale (float): Initial scale for the custom object.

    Returns:
        tuple: A tuple containing (curve_path_obj, animated_obj).
    """
    curve_path_obj = None
    animated_obj = None

    try:
        curve = bpy.data.curves.new(name = "data_curve", type = 'CURVE')
        curve.dimensions = '3D'
        curve_path_obj = bpy.data.objects.new("my_curve", curve)

        bezier_curve = curve.splines.new('BEZIER')
        if display_data:
            bezier_curve.bezier_points.add(len(display_data)-1)
        else:
            bezier_curve.bezier_points.add(0)

        current_position_x = graph_start_position
        for i, data in enumerate(display_data):
            if i < len(bezier_curve.bezier_points):
                bezier = bezier_curve.bezier_points[i]
                bezier.co = (current_position_x, 0, data) # Initial position on Y=0
                current_position_x += x_axis_spread # Use x_axis_spread here

        context.scene.collection.objects.link(curve_path_obj)
        curve_path_obj.select_set(True)
        context.view_layer.objects.active = curve_path_obj
        bpy.ops.object.editmode_toggle()
        bpy.ops.curve.select_all(action='SELECT')
        bpy.ops.curve.handle_type_set(type='AUTOMATIC')
        bpy.ops.object.editmode_toggle()

        curve_path_obj.data.materials.append(material_1)

        # Define Geometry Nodes for curve trimming
        geometry_nodes = bpy.data.node_groups.new(type = "GeometryNodeTree", name = "Curve_Animation_Nodes")
        if (MAJOR_VERSION >= 4):
            geometry_nodes.interface.new_socket('NodeInterfaceInput', in_out='INPUT', socket_type='NodeSocketGeometry')
            geometry_nodes.interface.new_socket('NodeInterfaceOutput', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        else:
            geometry_nodes.inputs.new("NodeSocketGeometry", "Geometry")
            geometry_nodes.outputs.new("NodeSocketGeometry", "Geometry")

        group_input = geometry_nodes.nodes.new("NodeGroupInput")
        group_input.location = (-340.0, 0.0)
        group_output = geometry_nodes.nodes.new("NodeGroupOutput")
        group_output.location = (609.8951416015625, 0.0)

        trim_curve = geometry_nodes.nodes.new("GeometryNodeTrimCurve")
        trim_curve.location = (-63.592041015625, 22.438913345336914)
        trim_curve.mode = 'FACTOR'
        trim_curve.inputs[1].default_value = True # Start factor is 0
        
        # Keyframes for curve animation (simplified to match reference)
        trim_curve.inputs[3].default_value = 0.0 # End factor starts at 0
        trim_curve.inputs[3].keyframe_insert('default_value', frame=anim_start_frame)
        trim_curve.inputs[3].default_value = 1.0 # End factor ends at 1
        trim_curve.inputs[3].keyframe_insert('default_value', frame=anim_end_frame)

        curve_to_mesh = geometry_nodes.nodes.new("GeometryNodeCurveToMesh")
        curve_to_mesh.location = (169.89512634277344, 18.004777908325195)

        curve_circle = geometry_nodes.nodes.new("GeometryNodeCurvePrimitiveCircle")
        curve_circle.location = (-340.7394104003906, -86.51416015625)
        curve_circle.mode = 'RADIUS'
        curve_circle.inputs[0].default_value = 32
        curve_circle.inputs[4].default_value = 0.03 # Radius for the profile curve

        set_material = geometry_nodes.nodes.new("GeometryNodeSetMaterial")
        set_material.location = (389.71429443359375, 25.688528060913086)
        set_material.inputs[2].default_value = material_1

        # Link nodes
        geometry_nodes.links.new(set_material.outputs[0], group_output.inputs[0])
        geometry_nodes.links.new(group_input.outputs[0], trim_curve.inputs[0])
        geometry_nodes.links.new(trim_curve.outputs[0], curve_to_mesh.inputs[0])
        geometry_nodes.links.new(curve_circle.outputs[0], curve_to_mesh.inputs[1])
        geometry_nodes.links.new(curve_to_mesh.outputs[0], set_material.inputs[0])
        
        # Set interpolation for the specific F-curve of the Trim Curve node
        if geometry_nodes.animation_data and geometry_nodes.animation_data.action:
            fcurve_trim = geometry_nodes.animation_data.action.fcurves.find('nodes["Trim Curve"].inputs[3].default_value')
            if fcurve_trim:
                for kf in fcurve_trim.keyframe_points:
                    kf.interpolation = 'LINEAR'
                    kf.easing = 'AUTO'
                print("Trim Curve F-curve interpolation set to LINEAR.")
            else:
                print("Warning: Trim Curve F-curve not found on node group action after keyframe insertion.")
        else:
            print("Warning: Geometry Nodes animation data or action not found after keyframe insertion.")

        modifier = curve_path_obj.modifiers.new("Curve_Reveal_Nodes", "NODES")
        modifier.node_group = geometry_nodes
        print("Geometry Nodes modifier for curve reveal added.")

        # Create the custom animated object (replaces the sphere)
        if object_type == 'CUBE':
            bpy.ops.mesh.primitive_cube_add(size=1)
        elif object_type == 'CONE':
            bpy.ops.mesh.primitive_cone_add(radius=0.5, depth=1)
        elif object_type == 'CYLINDER':
            bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1)
        else: # Default to cube if unknown type
            bpy.ops.mesh.primitive_cube_add(size=1)
            print(f"Warning: Unknown object type '{object_type}'. Defaulting to CUBE.")

        animated_obj = context.active_object
        animated_obj.name = object_name
        animated_obj.location = [0,0,0] # Initial location, will be overridden by constraint
        animated_obj.scale = [object_scale, object_scale, object_scale] # Apply initial scale
        animated_obj.data.materials.append(material_1)

        # Add Follow Path constraint to the animated object
        follow_path = animated_obj.constraints.new(type='FOLLOW_PATH')
        follow_path.target = curve_path_obj
        follow_path.forward_axis = 'TRACK_NEGATIVE_Z'
        follow_path.up_axis = 'UP_Y'
        follow_path.use_fixed_location = True
        follow_path.offset_factor = 0.0
        follow_path.keyframe_insert("offset_factor", frame=anim_start_frame)
        follow_path.offset_factor = 1.0
        follow_path.keyframe_insert("offset_factor", frame=anim_end_frame)

        # Set interpolation for animated object's follow path
        if animated_obj.animation_data and animated_obj.animation_data.action:
            fcurves = animated_obj.animation_data.action.fcurves
            for fcurve in fcurves:
                for kf in fcurve.keyframe_points:
                    kf.interpolation = 'LINEAR'
                    kf.easing = 'AUTO'
        bpy.ops.constraint.followpath_path_animate(constraint=follow_path.name)
        print(f"Animated object '{animated_obj.name}' created and set to follow '{curve_path_obj.name}'.")

    except Exception as e:
        print(f"Error creating curve or animated object: {e}")
        traceback.print_exc()
        print("Curve and animated object might not be generated.")
    
    return curve_path_obj, animated_obj

def create_data_points_and_text(data_list, month_list, display_data, graph_start_position, x_axis_spread, anim_start_frame, anim_length_data, currency_symbol, material_2):
    """
    Creates animated text labels for each data point.

    Args:
        data_list (list): Original numerical data.
        month_list (list): Month/category labels.
        display_data (list): Normalized data for display heights.
        graph_start_position (float): Starting X-coordinate.
        x_axis_spread (float): Distance between points.
        anim_start_frame (int): Start frame for animations.
        anim_length_data (int): Length of animation for each data point.
        currency_symbol (str): Symbol to prepend to data values.
        material_2 (bpy.types.Material): Material for text labels.
    """
    anim_length_text = anim_length_data / 2
    anim_curr_frame = anim_start_frame

    for data_counter in range(len(data_list)):
        try:
            text_month = str(month_list[data_counter])
            text_data = currency_symbol + str(data_list[data_counter])
            
            # Add the 1st caption (month)
            bpy.ops.object.text_add()
            ob_month = bpy.context.object
            ob_month.data.body = text_month
            ob_month.data.align_x = "CENTER"
            ob_month.data.align_y = "CENTER"
            ob_month.data.extrude = 0.01

            ob_month.location = [graph_start_position + x_axis_spread * data_counter, 0, display_data[data_counter] + 1.5] # Use x_axis_spread here
            ob_month.rotation_euler = [math.radians(90),0,0]
            
            # Animate the caption scale to appear immediately
            ob_month.scale = [0,0,0]
            ob_month.keyframe_insert(data_path="scale", frame = anim_curr_frame - 1) # Invisible just before
            ob_month.scale = [0.5,0.5,0.5]
            ob_month.keyframe_insert(data_path="scale", frame = anim_curr_frame) # Visible immediately
            
            # Assign the material
            ob_month.data.materials.append(material_2)
            
            # Add the 2nd caption (data value)
            bpy.ops.object.text_add()
            ob_data = context.active_object
            ob_data.data.body = text_data
            ob_data.data.align_x = "CENTER"
            ob_data.data.align_y = "CENTER"
            ob_data.data.extrude = 0.01

            ob_data.location = [graph_start_position + x_axis_spread * data_counter, 0, display_data[data_counter] + 1] # Use x_axis_spread here
            ob_data.rotation_euler = [math.radians(90),0,0]

            # Animate the caption scale to appear immediately
            ob_data.scale = [0,0,0]
            ob_data.keyframe_insert(data_path="scale", frame = anim_curr_frame - 1) # Invisible just before
            ob_data.scale = [0.5,0.5,0.5]
            ob_data.keyframe_insert(data_path="scale", frame = anim_curr_frame) # Visible immediately
            
            # Assign the material
            ob_data.data.materials.append(material_2)
            
            anim_curr_frame += anim_length_data # Advance frame for next data point
        except Exception as e:
            print(f"Error creating text/sphere for data point {data_counter}: {e}")
            traceback.print_exc()
            print("Skipping this data point and continuing.")

def create_axes(display_data, graph_start_position, x_axis_spread, number_of_data, material_3, material_4): # x_axis_spread parameter added
    """
    Creates the X and Z axes for the graph.

    Args:
        display_data (list): Normalized data points to determine Z-axis height.
        graph_start_position (float): Starting X-coordinate.
        x_axis_spread (float): Distance between points.
        number_of_data (int): Total number of data points.
        material_3 (bpy.types.Material): Material for the X-axis.
        material_4 (bpy.types.Material): Material for the Z-axis.
    """
    try:
        # X-axis
        bpy.ops.mesh.primitive_cube_add()
        ob_x_axis = context.active_object
        axis_length = graph_start_position + x_axis_spread * (number_of_data - 1) + 2 if number_of_data > 0 else 2 # Use x_axis_spread here
        ob_x_axis.dimensions = [axis_length,0.05,0.05]
        ob_x_axis.location = [axis_length/2,0,0]
        ob_x_axis.data.materials.append(material_3)

        bpy.ops.mesh.primitive_cylinder_add(vertices = 3, radius = 0.3, depth = 0.1)
        cyl1 = context.active_object
        cyl1.location = [axis_length, 0, 0]
        cyl1.scale = [1,1.7,1]
        cyl1.rotation_euler = [0,math.radians(90),-math.radians(90)]
        cyl1.data.materials.append(material_3)

        # Z-axis
        bpy.ops.mesh.primitive_cube_add()
        ob_z_axis = context.active_object
        axis_height = max(display_data) + 3 if display_data else 3
        ob_z_axis.dimensions = [0.05,0.05,axis_height]
        ob_z_axis.location = [0,0,axis_height/2]
        ob_z_axis.data.materials.append(material_4)

        bpy.ops.mesh.primitive_cylinder_add(vertices = 3, radius = 0.3, depth = 0.1)
        cyl2 = context.active_object
        cyl2.location = [0, 0, axis_height]
        cyl2.scale = [1,1.7,1]
        cyl2.rotation_euler = [math.radians(90),0,0]
        cyl2.data.materials.append(material_4)
        print("Axes created successfully.")
    except Exception as e:
        print(f"Error creating axes: {e}")
        traceback.print_exc()
        print("Axes might not be generated correctly.")


def setup_camera_animation(curve_path_obj, animated_obj, anim_start_frame, anim_end_frame, number_of_data, x_axis_spread):
    """
    Sets up the camera to follow the generated curve with dynamic angles and focus on the animated object.

    Args:
        curve_path_obj (bpy.types.Object): The curve object the camera will follow.
        animated_obj (bpy.types.Object): The animated object (ball) that the camera will focus on.
        anim_start_frame (int): The frame at which the camera animation starts.
        anim_end_frame (int): The frame at which the camera animation ends.
        number_of_data (int): Total number of data points (to determine path length).
        x_axis_spread (float): Distance between data points on the X-axis.
    """
    # Get the active camera, or create one if none exists
    camera_obj = bpy.context.scene.camera
    if camera_obj is None:
        bpy.ops.object.camera_add(location=(0, 0, 0)) # Add at origin temporarily
        camera_obj = bpy.context.active_object
        camera_obj.name = "Graph_Camera"
        bpy.context.scene.camera = camera_obj # Set as active scene camera
        print("New camera created and set as active scene camera.")
    else:
        print("Using existing active camera for animation.")

    # Clear existing animation data on the camera to avoid conflicts
    if camera_obj.animation_data:
        camera_obj.animation_data_clear()

    # Set camera lens (focal length) for a wider field of view
    camera_obj.data.lens = 25.0 # A common wide-angle lens (e.g., 25mm)
    print(f"Camera lens set to {camera_obj.data.lens}mm for wider view.")

    # --- Add Follow Path constraint to the Camera ---
    follow_path_constraint = camera_obj.constraints.new(type='FOLLOW_PATH')
    follow_path_constraint.target = curve_path_obj
    # Camera's local -Y axis points along the path, Z is up. This is the "forward" direction.
    follow_path_constraint.forward_axis = 'TRACK_NEGATIVE_Y' 
    follow_path_constraint.up_axis = 'UP_Z' 
    follow_path_constraint.use_fixed_location = True # Ensures it stays on the path

    # Animate the offset factor for the camera's movement along the path
    follow_path_constraint.offset_factor = 0.0
    follow_path_constraint.keyframe_insert("offset_factor", frame=anim_start_frame)
    follow_path_constraint.offset_factor = 1.0
    follow_path_constraint.keyframe_insert("offset_factor", frame=anim_end_frame)

    # Set interpolation to linear for smooth, consistent movement along path
    if camera_obj.animation_data and camera_obj.animation_data.action:
        fcurves_cam_path = camera_obj.animation_data.action.fcurves.find('constraints["Follow Path"].offset_factor')
        if fcurves_cam_path:
            for kf in fcurves_cam_path.keyframe_points:
                kf.interpolation = 'LINEAR'
                kf.easing = 'AUTO'

    # --- Add "Track To" constraint to the Camera, targeting the Animated Object ---
    track_to_constraint = camera_obj.constraints.new(type='TRACK_TO')
    track_to_constraint.target = animated_obj # DIRECTLY TARGET THE ANIMATED OBJECT
    track_to_constraint.track_axis = 'TRACK_NEGATIVE_Z' # Camera's -Z points to target
    track_to_constraint.up_axis = 'UP_Y' # Camera's Y is its up axis
    print("Camera 'Track To' constraint added, targeting the animated object.")

    # --- Define a set of dynamic camera poses (relative to the path) ---
    # Each pose is (local_offset_x, local_offset_y, local_offset_z)
    # local_offset_y: Negative values are behind the path, positive are in front.
    # The camera's rotation is now handled by the Track To constraint.
    dynamic_poses = [
        # Pose 1: Wide shot, slightly closer behind and above
        (0, -20, 5), # Was -25, 6

        # Pose 2: Closer, slightly to the right
        (5, -15, 3.5), # Was -18, 4

        # Pose 3: Slightly closer back, higher (overview)
        (0, -30, 7), # Was -35, 8

        # Pose 4: Closer, slightly to the left
        (-5, -15, 3.5), # Was -18, 4

        # Pose 5: Medium distance, directly behind, slightly closer
        (0, -17, 4.5), # Was -20, 5

        # Pose 6: Slightly in front, looking back (camera moves ahead, but looks back at the object)
        (0, 7, 2.5), # Was 8, 3

        # Pose 7: Side view (right), slightly closer distance
        (7, -12, 3), # Was 8, -15, 3.5

        # Pose 8: Side view (left), slightly closer distance
        (-7, -12, 3), # Was -8, -15, 3.5
        
        # Added more subtle variations for smoother transitions, adjusted for closer distance
        (0, -18, 5), # Was -22, 5.5
        (2.5, -16, 3.8), # Was 3, -19, 4.2
        (-2.5, -16, 3.8), # Was -3, -19, 4.2
        (0, -8, 2.5), # Was -10, 3 (Even closer view)
        (0, -24, 6.5), # Was -28, 7 (Slightly further back, but still closer than original)
    ]
    
    segment_length = ANIM_LENGTH_DATA # Frames per data point

    # Initial pose at anim_start_frame
    initial_loc = dynamic_poses[0]
    camera_obj.location = initial_loc
    camera_obj.keyframe_insert('location', frame=anim_start_frame)
    
    # Cycle through dynamic poses for each data point
    for i in range(number_of_data):
        current_frame = anim_start_frame + (i + 1) * segment_length
        
        # Get the next pose in the cycle
        pose_index = (i + 1) % len(dynamic_poses)
        next_loc = dynamic_poses[pose_index]

        # Keyframe camera's local position
        camera_obj.location = next_loc
        camera_obj.keyframe_insert('location', frame=current_frame)
        
    # Ensure all newly added keyframes for location have LINEAR interpolation
    if camera_obj.animation_data and camera_obj.animation_data.action:
        for fcurve in camera_obj.animation_data.action.fcurves:
            if fcurve.data_path.startswith('location'):
                for kf in fcurve.keyframe_points:
                    kf.interpolation = 'LINEAR'
                    kf.easing = 'AUTO'
    
    print("Camera animation setup complete with dynamic angles and improved focus.")


def setup_scene_settings(anim_end_frame):
    """
    Configures global Blender scene settings.

    Args:
        anim_end_frame (int): The calculated end frame for the animation.
    """
    scene.frame_set(1)
    scene.frame_start = 1
    scene.frame_end = anim_end_frame + 50 # Add some buffer frames

    if MAJOR_VERSION >= 4 and MINOR_VERSION >= 1:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
        print("Set render engine to BLENDER_EEVEE_NEXT.")
    else:
        scene.render.engine = 'BLENDER_EEVEE'
        print("Set render engine to BLENDER_EEVEE.")

    print("Note: Automatic Bloom enabling via script has been disabled for compatibility.")
    print("You can manually enable Bloom in Blender's Render Properties if desired.")

    print("Scene settings configured.")

def main():
    """
    Main function to orchestrate the 3D graph generation and animation.
    """
    # Save the current location of the 3D cursor
    saved_cursor_loc = scene.cursor.location.xyz

    # 1. Read Data
    data_list, month_list, number_of_data = read_csv_data(CSV_FILE_PATH, DATA_COLUMN, MONTH_COLUMN)

    if number_of_data == 0:
        print("No valid data found in the CSV file. Exiting script gracefully.")
        return

    # 2. Normalize Data
    display_data = normalize_and_display_data(data_list)

    # Calculate animation end frame based on data length
    if number_of_data > 1:
        anim_end_frame = ANIM_START_FRAME + ANIM_LENGTH_DATA * (number_of_data - 1)
    else:
        anim_end_frame = ANIM_START_FRAME + ANIM_LENGTH_DATA

    # 3. Setup Materials
    material_1, material_2, material_3, material_4 = setup_materials()

    # 4. Create Curve and Animated Object
    # The animated object now replaces the sphere and the road mesh visually.
    curve_path_obj, animated_obj = create_curve_and_animated_object(
        display_data, GRAPH_START_POSITION, X_AXIS_SPREAD, # Use X_AXIS_SPREAD here
        ANIM_START_FRAME, anim_end_frame, material_1,
        ANIMATED_OBJECT_TYPE, ANIMATED_OBJECT_NAME, ANIMATED_OBJECT_SCALE
    )

    # 5. Create Data Points and Text
    create_data_points_and_text(data_list, month_list, display_data, GRAPH_START_POSITION, X_AXIS_SPREAD, ANIM_START_FRAME, ANIM_LENGTH_DATA, CURRENCY_SYMBOL, material_2) # Use X_AXIS_SPREAD here

    # 6. Create Axes - COMMENTED OUT TO REMOVE AXES
    # create_axes(display_data, GRAPH_START_POSITION, X_AXIS_SPREAD, number_of_data, material_3, material_4) # x_axis_spread parameter added
    
    # Removed: 7. Create Ground Plane
    # create_ground_plane((material_1, material_2, material_3, material_4)) # Pass materials tuple

    # 7. Setup Camera Animation (re-numbered)
    # Pass animated_obj to the camera setup function
    if curve_path_obj and animated_obj: 
        setup_camera_animation(curve_path_obj, animated_obj, ANIM_START_FRAME, anim_end_frame, number_of_data, X_AXIS_SPREAD)
    else:
        print("Skipping camera animation: Curve object or animated object not found.")

    # 8. Setup Scene Settings (re-numbered)
    setup_scene_settings(anim_end_frame)

    # Clean-up work
    scene.cursor.location.xyz = saved_cursor_loc
    # Deselect all objects at the end, if any are active
    bpy.ops.object.select_all(action='DESELECT')


    print("\n3D Curved Graph generation attempt complete. Check console for any errors.")
    print(f"Animation runs from frame {scene.frame_start} to {scene.frame_end}.")

# Run the main function
if __name__ == "__main__":
    main()