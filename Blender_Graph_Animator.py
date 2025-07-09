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


CSV_FILE_PATH = r"C:\Data\Database.csv"  # <--- VERIFY THIS PATH CAREFULLY
DATA_COLUMN = 3  # 1-indexed column number for numerical data
MONTH_COLUMN = 2  # 1-indexed column number for category/month labels
CURRENCY_SYMBOL = "$"


GRAPH_ANIM_START_FRAME = 2
GRAPH_ANIM_LENGTH_DATA = 100  # Adjusted: Made twice as slow (100 * 2 = 200)
GRAPH_START_POSITION = 0
GRAPH_X_AXIS_SPREAD = 2  # Increased distance between points for wider bases


# Custom Animated Object Settings for Graph
ANIMATED_OBJECT_TYPE = "CYLINDER"  # Choose 'CUBE', 'CONE', or 'CYLINDER'
ANIMATED_OBJECT_NAME = "Animated_Graph_Object"
ANIMATED_OBJECT_SCALE = 0.1  # Initial scale for the custom object


# NEW CONFIGURATION: Control whether to rebuild the graph if it already exists
# Set to True to force a complete rebuild (clears existing graph objects).
# Set to False to preserve existing graph objects and their transformations on subsequent runs.
REBUILD_GRAPH_ON_RUN = False  # <--- IMPORTANT CHANGE


# General Script Settings (for this script only)
SAVE_TEMPLATE_BLEND = False
TEMPLATE_SAVE_PATH = r"C:\BlenderTemplates\MyGraphTemplate.blend"


# --- END USER CONFIGURATION ---


def print_debug_info(message):
    """Helper function to print debug information."""
    print(f"[DEBUG] {message}")


def read_csv_data(csv_file_path, data_column, month_column):
    """
    Reads numerical data and month labels from a specified CSV file.
    """
    data_list = []
    month_list = []
    number_of_data = 0

    if not os.path.exists(csv_file_path):
        print(f"Error: CSV file NOT found at specified path: {csv_file_path}")
        print("Please ensure the 'csv_file_path' variable in the script is correct.")
        return [], [], 0

    try:
        with open(csv_file_path, "r", newline="") as file:
            csvreader = csv.reader(file)
            header = next(csvreader)  # Read header row

            # Basic validation for column indices
            if not (1 <= data_column <= len(header)):
                print(
                    f"Error: data_column ({data_column}) is out of bounds. Header has {len(header)} columns."
                )
                return [], [], 0
            if not (1 <= month_column <= len(header)):
                print(
                    f"Error: month_column ({month_column}) is out of bounds. Header has {len(header)} columns."
                )
                return [], [], 0

            print(f"Reading CSV from: {csv_file_path}")
            print(f"Header: {header}")
            print(
                f"Using data from column '{header[data_column-1]}' (index {data_column-1})"
            )
            print(
                f"Using month from column '{header[month_column-1]}' (index {month_column-1})"
            )

            for row_idx, row in enumerate(csvreader):
                if len(row) >= max(data_column, month_column):
                    try:
                        data_value = float(row[data_column - 1])
                        data_list.append(data_value)
                        month_list.append(str(row[month_column - 1]))
                    except ValueError:
                        print(
                            f"Warning: Non-numeric data found in data_column at row {row_idx+2}. Skipping row."
                        )
                    except IndexError:
                        print(
                            f"Warning: Row {row_idx+2} has fewer columns than expected. Skipping row."
                        )
                else:
                    print(
                        f"Warning: Row {row_idx+2} has too few columns. Skipping row."
                    )

        number_of_data = len(month_list)
        print(f"Successfully read {number_of_data} data points from CSV.")
        return data_list, month_list, number_of_data

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        print(
            "Please ensure the 'csv_file_path' is correct and the CSV format is valid."
        )
        traceback.print_exc()
        return [], [], 0


def normalize_and_display_data(data_list):
    """
    Normalizes the input data list for display purposes in Blender.
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
    if data_height_min < 0:  # Only adjust if there are negative values
        offset = abs(data_height_min)
        for data in normalized_data:
            display_data.append(data + offset)
    else:
        display_data = normalized_data[:]  # Create a copy

    return display_data


def setup_materials():
    """
    Creates and configures all necessary materials for the graph.
    """
    materials = {}

    # Material 1 (Curve and Sphere/Animated Object)
    material_1 = bpy.data.materials.new(name="graph_material_1")
    material_1.use_nodes = True
    nodes = material_1.node_tree.nodes
    links = material_1.node_tree.links
    nodes.clear()  # Clear existing nodes
    output = nodes.new(type="ShaderNodeOutputMaterial")
    shader = nodes.new(type="ShaderNodeEmission")
    shader.inputs["Color"].default_value = (1.0, 0.3, 0.0, 1)  # Orange
    shader.inputs["Strength"].default_value = 1.5
    links.new(shader.outputs[0], output.inputs[0])
    materials["material_1"] = material_1

    # Material 2 (Text)
    material_2 = bpy.data.materials.new(name="graph_material_2")
    material_2.use_nodes = True
    nodes = material_2.node_tree.nodes
    links = material_2.node_tree.links
    nodes.clear()
    output = nodes.new(type="ShaderNodeOutputMaterial")
    shader = nodes.new(type="ShaderNodeEmission")
    shader.inputs["Strength"].default_value = 3.0  # Brighter white
    links.new(shader.outputs[0], output.inputs[0])
    materials["material_2"] = material_2

    # Material 3 (X-axis)
    material_3 = bpy.data.materials.new(name="graph_material_3")
    material_3.use_nodes = True
    nodes = material_3.node_tree.nodes
    links = material_3.node_tree.links
    nodes.clear()
    output = nodes.new(type="ShaderNodeOutputMaterial")
    shader = nodes.new(type="ShaderNodeBsdfPrincipled")
    shader.inputs[0].default_value = (1.0, 0.05, 0.135, 1)  # Reddish
    links.new(shader.outputs[0], output.inputs[0])
    materials["material_3"] = material_3

    # Material 4 (Z-axis)
    material_4 = bpy.data.materials.new(name="graph_material_4")
    material_4.use_nodes = True
    nodes = material_4.node_tree.nodes
    links = material_4.node_tree.links
    nodes.clear()
    output = nodes.new(type="ShaderNodeOutputMaterial")
    shader = nodes.new(type="ShaderNodeBsdfPrincipled")
    shader.inputs[0].default_value = (0.0, 0.24, 0.6, 1)  # Blueish
    links.new(shader.outputs[0], output.inputs[0])
    materials["material_4"] = material_4

    return (
        materials["material_1"],
        materials["material_2"],
        materials["material_3"],
        materials["material_4"],
    )


def create_curve_and_animated_object(
    display_data,
    graph_start_position,
    x_axis_spread,
    anim_start_frame,
    anim_end_frame,
    material_1,
    object_type,
    object_name,
    object_scale,
    parent_empty,
    target_collection,
):
    """
    Creates the 3D curve based on data and a custom object that follows it.
    The curve's animation (trimming) is handled by Geometry Nodes.
    """
    curve_path_obj = None
    animated_obj = None

    try:
        curve = bpy.data.curves.new(name="data_curve", type="CURVE")
        curve.dimensions = "3D"
        curve_path_obj = bpy.data.objects.new("my_curve", curve)

        bezier_curve = curve.splines.new("BEZIER")
        if display_data:
            bezier_curve.bezier_points.add(len(display_data) - 1)
        else:
            bezier_curve.bezier_points.add(0)

        current_position_x = graph_start_position
        for i, data in enumerate(display_data):
            if i < len(bezier_curve.bezier_points):
                bezier = bezier_curve.bezier_points[i]
                bezier.co = (current_position_x, 0, data)  # Initial position on Y=0
                current_position_x += x_axis_spread  # Use x_axis_spread here

        # Link to target collection and parent
        # First, unlink from any default collections it might have been linked to
        for coll in list(curve_path_obj.users_collection):
            coll.objects.unlink(curve_path_obj)
        target_collection.objects.link(curve_path_obj)

        curve_path_obj.parent = parent_empty
        curve_path_obj.matrix_parent_inverse = parent_empty.matrix_world.inverted()

        # Set active object for edit mode (temporarily)
        bpy.context.view_layer.objects.active = curve_path_obj
        bpy.ops.object.editmode_toggle()
        bpy.ops.curve.select_all(action="SELECT")
        bpy.ops.curve.handle_type_set(type="AUTOMATIC")
        bpy.ops.object.editmode_toggle()

        curve_path_obj.data.materials.append(material_1)

        # Define Geometry Nodes for curve trimming
        geometry_nodes = bpy.data.node_groups.new(
            type="GeometryNodeTree", name="Curve_Animation_Nodes"
        )
        if MAJOR_VERSION >= 4:
            geometry_nodes.interface.new_socket(
                "NodeInterfaceInput", in_out="INPUT", socket_type="NodeSocketGeometry"
            )
            geometry_nodes.interface.new_socket(
                "NodeInterfaceOutput", in_out="OUTPUT", socket_type="NodeSocketGeometry"
            )
        else:
            geometry_nodes.inputs.new("NodeSocketGeometry", "Geometry")
            geometry_nodes.outputs.new("NodeSocketGeometry", "Geometry")

        group_input = geometry_nodes.nodes.new("NodeGroupInput")
        group_input.location = (-340.0, 0.0)
        group_output = geometry_nodes.nodes.new("NodeGroupOutput")
        group_output.location = (609.8951416015625, 0.0)

        trim_curve = geometry_nodes.nodes.new("GeometryNodeTrimCurve")
        trim_curve.location = (-63.592041015625, 22.438913345336914)
        trim_curve.mode = "FACTOR"
        trim_curve.inputs[1].default_value = True  # Start factor is 0

        # Keyframes for curve animation
        trim_curve.inputs[3].default_value = 0.0  # End factor starts at 0
        trim_curve.inputs[3].keyframe_insert("default_value", frame=anim_start_frame)
        trim_curve.inputs[3].default_value = 1.0  # End factor ends at 1
        trim_curve.inputs[3].keyframe_insert("default_value", frame=anim_end_frame)

        curve_to_mesh = geometry_nodes.nodes.new("GeometryNodeCurveToMesh")
        curve_to_mesh.location = (169.89512634277344, 18.004777908325195)

        curve_circle = geometry_nodes.nodes.new("GeometryNodeCurvePrimitiveCircle")
        curve_circle.location = (-340.7394104003906, -86.51416015625)
        curve_circle.mode = "RADIUS"
        curve_circle.inputs[0].default_value = 32
        curve_circle.inputs[4].default_value = 0.03  # Radius for the profile curve

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
            fcurve_trim = geometry_nodes.animation_data.action.fcurves.find(
                'nodes["Trim Curve"].inputs[3].default_value'
            )
            if fcurve_trim:
                for kf in fcurve_trim.keyframe_points:
                    kf.interpolation = "LINEAR"
                    kf.easing = "AUTO"
                print("Trim Curve F-curve interpolation set to LINEAR.")
            else:
                print(
                    "Warning: Trim Curve F-curve not found on node group action after keyframe insertion."
                )
        else:
            print(
                "Warning: Geometry Nodes animation data or action not found after keyframe insertion."
            )

        modifier = curve_path_obj.modifiers.new("Curve_Reveal_Nodes", "NODES")
        modifier.node_group = geometry_nodes
        print("Geometry Nodes modifier for curve reveal added.")

        # Create the custom animated object (replaces the sphere)
        if object_type == "CUBE":
            bpy.ops.mesh.primitive_cube_add(size=1)
        elif object_type == "CONE":
            bpy.ops.mesh.primitive_cone_add(radius=0.5, depth=1)
        elif object_type == "CYLINDER":
            bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1)
        else:  # Default to cube if unknown type
            bpy.ops.mesh.primitive_cube_add(size=1)
            print(f"Warning: Unknown object type '{object_type}'. Defaulting to CUBE.")

        animated_obj = bpy.context.active_object
        animated_obj.name = object_name
        animated_obj.location = [
            0,
            0,
            0,
        ]  # Initial location, will be overridden by constraint
        animated_obj.scale = [
            object_scale,
            object_scale,
            object_scale,
        ]  # Apply initial scale
        animated_obj.data.materials.append(material_1)

        # Link to target collection and parent
        # First, unlink from any default collections it might have been linked to
        for coll in list(animated_obj.users_collection):
            coll.objects.unlink(animated_obj)
        target_collection.objects.link(animated_obj)

        animated_obj.parent = parent_empty
        animated_obj.matrix_parent_inverse = parent_empty.matrix_world.inverted()

        # Add Follow Path constraint to the animated object
        follow_path = animated_obj.constraints.new(type="FOLLOW_PATH")
        follow_path.target = curve_path_obj
        follow_path.forward_axis = "TRACK_NEGATIVE_Z"
        follow_path.up_axis = "UP_Y"
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
                    kf.interpolation = "LINEAR"
                    kf.easing = "AUTO"
        bpy.ops.constraint.followpath_path_animate(constraint=follow_path.name)
        print(
            f"Animated object '{animated_obj.name}' created and set to follow '{curve_path_obj.name}'."
        )

    except Exception as e:
        print(f"Error creating curve or animated object: {e}")
        traceback.print_exc()
        print("Curve and animated object might not be generated.")

    return curve_path_obj, animated_obj


def create_data_points_and_text(
    data_list,
    month_list,
    display_data,
    graph_start_position,
    x_axis_spread,
    anim_start_frame,
    anim_length_data,
    currency_symbol,
    material_2,
    parent_empty,
    target_collection,
):
    """
    Creates animated text labels for each data point.
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

            ob_month.location = [
                graph_start_position + x_axis_spread * data_counter,
                0,
                display_data[data_counter] + 1.5,
            ]
            ob_month.rotation_euler = [math.radians(90), 0, 0]

            # Animate the caption scale to appear immediately
            ob_month.scale = [0, 0, 0]
            ob_month.keyframe_insert(data_path="scale", frame=anim_curr_frame - 1)
            ob_month.scale = [0.5, 0.5, 0.5]
            ob_month.keyframe_insert(data_path="scale", frame=anim_curr_frame)

            # Assign the material
            ob_month.data.materials.append(material_2)

            # Link to target collection and parent
            # First, unlink from any default collections it might have been linked to
            for coll in list(ob_month.users_collection):
                coll.objects.unlink(ob_month)
            target_collection.objects.link(ob_month)

            ob_month.parent = parent_empty
            ob_month.matrix_parent_inverse = parent_empty.matrix_world.inverted()

            # Add the 2nd caption (data value)
            bpy.ops.object.text_add()
            ob_data = bpy.context.object
            ob_data.data.body = text_data
            ob_data.data.align_x = "CENTER"
            ob_data.data.align_y = "CENTER"
            ob_data.data.extrude = 0.01

            ob_data.location = [
                graph_start_position + x_axis_spread * data_counter,
                0,
                display_data[data_counter] + 1,
            ]
            ob_data.rotation_euler = [math.radians(90), 0, 0]

            # Animate the caption scale to appear immediately
            ob_data.scale = [0, 0, 0]
            ob_data.keyframe_insert(data_path="scale", frame=anim_curr_frame - 1)
            ob_data.scale = [0.5, 0.5, 0.5]
            ob_data.keyframe_insert(data_path="scale", frame=anim_curr_frame)

            # Assign the material
            ob_data.data.materials.append(material_2)

            # Link to target collection and parent
            # First, unlink from any default collections it might have been linked to
            for coll in list(ob_data.users_collection):
                coll.objects.unlink(ob_data)
            target_collection.objects.link(ob_data)

            ob_data.parent = parent_empty
            ob_data.matrix_parent_inverse = parent_empty.matrix_world.inverted()

            anim_curr_frame += anim_length_data  # Advance frame for next data point
        except Exception as e:
            print(f"Error creating text/sphere for data point {data_counter}: {e}")
            traceback.print_exc()
            print("Skipping this data point and continuing.")


def create_axes(
    display_data,
    graph_start_position,
    x_axis_spread,
    number_of_data,
    material_3,
    material_4,
    parent_empty,
    target_collection,
):
    """
    Creates the X and Z axes for the graph.
    """
    try:
        # X-axis
        bpy.ops.mesh.primitive_cube_add()
        ob_x_axis = bpy.context.active_object
        axis_length = (
            graph_start_position + x_axis_spread * (number_of_data - 1) + 2
            if number_of_data > 0
            else 2
        )
        ob_x_axis.dimensions = [axis_length, 0.05, 0.05]
        ob_x_axis.location = [axis_length / 2, 0, 0]
        ob_x_axis.data.materials.append(material_3)

        # First, unlink from any default collections it might have been linked to
        for coll in list(ob_x_axis.users_collection):
            coll.objects.unlink(ob_x_axis)
        target_collection.objects.link(ob_x_axis)

        ob_x_axis.parent = parent_empty
        ob_x_axis.matrix_parent_inverse = parent_empty.matrix_world.inverted()

        bpy.ops.mesh.primitive_cylinder_add(vertices=3, radius=0.3, depth=0.1)
        cyl1 = bpy.context.active_object
        cyl1.location = [axis_length, 0, 0]
        cyl1.scale = [1, 1.7, 1]
        cyl1.rotation_euler = [0, math.radians(90), -math.radians(90)]
        cyl1.data.materials.append(material_3)

        # First, unlink from any default collections it might have been linked to
        for coll in list(cyl1.users_collection):
            coll.objects.unlink(cyl1)
        target_collection.objects.link(cyl1)

        cyl1.parent = parent_empty
        cyl1.matrix_parent_inverse = parent_empty.matrix_world.inverted()

        # Z-axis
        bpy.ops.mesh.primitive_cube_add()
        ob_z_axis = bpy.context.active_object
        axis_height = max(display_data) + 3 if display_data else 3
        ob_z_axis.dimensions = [0.05, 0.05, axis_height]
        ob_z_axis.location = [0, 0, axis_height / 2]
        ob_z_axis.data.materials.append(material_4)

        # First, unlink from any default collections it might have been linked to
        for coll in list(ob_z_axis.users_collection):
            coll.objects.unlink(ob_z_axis)
        target_collection.objects.link(ob_z_axis)

        ob_z_axis.parent = parent_empty
        ob_z_axis.matrix_parent_inverse = parent_empty.matrix_world.inverted()

        bpy.ops.mesh.primitive_cylinder_add(vertices=3, radius=0.3, depth=0.1)
        cyl2 = bpy.context.active_object
        cyl2.location = [0, 0, axis_height]
        cyl2.scale = [1, 1.7, 1]
        cyl2.rotation_euler = [math.radians(90), 0, 0]
        cyl2.data.materials.append(material_4)

        # First, unlink from any default collections it might have been linked to
        for coll in list(cyl2.users_collection):
            coll.objects.unlink(cyl2)
        target_collection.objects.link(cyl2)

        cyl2.parent = parent_empty
        cyl2.matrix_parent_inverse = parent_empty.matrix_world.inverted()
        print("Axes created successfully.")
    except Exception as e:
        print(f"Error creating axes: {e}")
        traceback.print_exc()
        print("Axes might not be generated correctly.")


def setup_camera_animation(
    curve_path_obj,
    animated_obj,
    anim_start_frame,
    anim_end_frame,
    number_of_data,
    x_axis_spread,
    target_collection,
):
    """
    Sets up the camera to follow the generated curve with dynamic angles and focus on the animated object.
    """
    # Get the active camera, or create one if none exists
    camera_obj = bpy.context.scene.camera
    if camera_obj is None:
        bpy.ops.object.camera_add(location=(0, 0, 0))  # Add at origin temporarily
        camera_obj = bpy.context.active_object
        camera_obj.name = "Graph_Camera"
        bpy.context.scene.camera = camera_obj  # Set as active scene camera
        print("New camera created and set as active scene camera.")
    else:
        print("Using existing active camera for animation.")

    # Link camera to the graph collection for better organization
    # First, unlink from any default collections it might have been linked to
    for coll in list(camera_obj.users_collection):
        coll.objects.unlink(camera_obj)
    target_collection.objects.link(camera_obj)

    # Clear existing animation data on the camera to avoid conflicts
    if camera_obj.animation_data:
        camera_obj.animation_data_clear()

    # Set camera lens (focal length) for a wider field of view
    camera_obj.data.lens = 25.0  # A common wide-angle lens (e.g., 25mm)
    print(f"Camera lens set to {camera_obj.data.lens}mm for wider view.")

    # --- Add Follow Path constraint to the Camera ---
    follow_path_constraint = camera_obj.constraints.new(type="FOLLOW_PATH")
    follow_path_constraint.target = curve_path_obj
    follow_path_constraint.forward_axis = "TRACK_NEGATIVE_Y"
    follow_path_constraint.up_axis = "UP_Z"
    follow_path_constraint.use_fixed_location = True  # Ensures it stays on the path

    # Animate the offset factor for the camera's movement along the path
    follow_path_constraint.offset_factor = 0.0
    follow_path_constraint.keyframe_insert("offset_factor", frame=anim_start_frame)
    follow_path_constraint.offset_factor = 1.0
    follow_path_constraint.keyframe_insert("offset_factor", frame=anim_end_frame)

    # Set interpolation to linear for smooth, consistent movement along path
    if camera_obj.animation_data and camera_obj.animation_data.action:
        fcurves_cam_path = camera_obj.animation_data.action.fcurves.find(
            'constraints["Follow Path"].offset_factor'
        )
        if fcurves_cam_path:
            for kf in fcurves_cam_path.keyframe_points:
                kf.interpolation = "LINEAR"
                kf.easing = "AUTO"

    # --- Add "Track To" constraint to the Camera, targeting the Animated Object ---
    track_to_constraint = camera_obj.constraints.new(type="TRACK_TO")
    track_to_constraint.target = animated_obj  # DIRECTLY TARGET THE ANIMATED OBJECT
    track_to_constraint.track_axis = "TRACK_NEGATIVE_Z"  # Camera's -Z points to target
    track_to_constraint.up_axis = "UP_Y"  # Camera's Y is its up axis
    print("Camera 'Track To' constraint added, targeting the animated object.")

    # --- Define a set of dynamic camera poses (relative to the path) ---
    dynamic_poses = [
        (0, -20, 5),
        (5, -15, 3.5),
        (0, -30, 7),
        (-5, -15, 3.5),
        (0, -17, 4.5),
        (0, 7, 2.5),
        (7, -12, 3),
        (-7, -12, 3),
        (0, -18, 5),
        (2.5, -16, 3.8),
        (-2.5, -16, 3.8),
        (0, -8, 2.5),
        (0, -24, 6.5),
    ]

    segment_length = GRAPH_ANIM_LENGTH_DATA  # Frames per data point

    # Initial pose at anim_start_frame
    initial_loc = dynamic_poses[0]
    camera_obj.location = initial_loc
    camera_obj.keyframe_insert("location", frame=anim_start_frame)

    # Cycle through dynamic poses for each data point
    for i in range(number_of_data):
        current_frame = anim_start_frame + (i + 1) * segment_length

        # Get the next pose in the cycle
        pose_index = (i + 1) % len(dynamic_poses)
        next_loc = dynamic_poses[pose_index]

        # Keyframe camera's local position
        camera_obj.location = next_loc
        camera_obj.keyframe_insert("location", frame=current_frame)

    # Ensure all newly added keyframes for location have LINEAR interpolation
    if camera_obj.animation_data and camera_obj.animation_data.action:
        for fcurve in camera_obj.animation_data.action.fcurves:
            if fcurve.data_path.startswith("location"):
                for kf in fcurve.keyframe_points:
                    kf.interpolation = "LINEAR"
                    kf.easing = "AUTO"

    print("Camera animation setup complete with dynamic angles and improved focus.")


def setup_scene_settings(anim_end_frame):
    """
    Configures global Blender scene settings.
    """
    bpy.context.scene.frame_set(1)
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = anim_end_frame + 50  # Add some buffer frames

    if MAJOR_VERSION >= 4 and MINOR_VERSION >= 1:
        bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
        print("Set render engine to BLENDER_EEVEE_NEXT.")
    else:
        bpy.context.scene.render.engine = "BLENDER_EEVEE"
        print("Set render engine to BLENDER_EEVEE.")

    print(
        "Note: Automatic Bloom enabling via script has been disabled for compatibility."
    )
    print("You can manually enable Bloom in Blender's Render Properties if desired.")

    print("Scene settings configured.")


class GraphAnimatorOperator(bpy.types.Operator):
    """Blender Operator to generate and animate a 3D graph."""
    bl_idname = "object.graph_animator"
    bl_label = "Generate Graph Animation"
    bl_options = {'REGISTER', 'UNDO'}

    # Operator properties to store state
    _saved_cursor_loc = None

    def execute(self, context):
        print("="*50)
        print("STARTING BLENDER GRAPH ANIMATOR SCRIPT")
        print("="*50)
        
        # Save the current location of the 3D cursor
        self._saved_cursor_loc = bpy.context.scene.cursor.location.xyz

        # Clear selection at the start to avoid unintended operations on existing objects
        bpy.ops.object.select_all(action='DESELECT')

        # Save background state before any operations
        background_collections = [
            coll for coll in bpy.data.collections 
            if "Background" in coll.name
        ]
        background_states = []
        for coll in background_collections:
            background_states.append({
                "name": coll.name,
                "hide_viewport": coll.hide_viewport,
                "hide_render": coll.hide_render,
                "objects": [obj.name for obj in coll.objects],
                "object_states": [
                    {
                        "name": obj.name,
                        "location": obj.location.copy(),
                        "rotation_euler": obj.rotation_euler.copy(),
                        "scale": obj.scale.copy()
                    }
                    for obj in coll.objects
                ]
            })

        # Create master empty for graph
        graph_master_empty = bpy.data.objects.get("Graph_Master")
        graph_collection = bpy.data.collections.get("Graph_Elements")

        # Determine if we should rebuild the graph or preserve existing one
        should_rebuild_graph = REBUILD_GRAPH_ON_RUN

        if graph_master_empty and graph_collection:
            # Heuristic: Check if the graph collection has objects other than the master empty/camera
            # to determine if it has been "built"
            has_existing_graph_content = any(obj.name not in ["Graph_Master", "Graph_Camera"] for obj in graph_collection.objects)

            if has_existing_graph_content and not should_rebuild_graph:
                print_debug_info("Existing 'Graph_Elements' found with content. Skipping graph generation to preserve manual changes.")
                self.report({'INFO'}, "Graph already exists. Set REBUILD_GRAPH_ON_RUN = True to force rebuild.")
                
                # If skipping, we still need to ensure the scene settings are correct
                # and camera animation is potentially updated (if it targets existing objects)
                # We also ensure the camera is linked to the graph collection if it exists
                camera_obj = bpy.context.scene.camera
                if camera_obj and camera_obj.name == "Graph_Camera":
                    # Ensure camera is linked to graph_collection if it's the one this script manages
                    if camera_obj.name not in graph_collection.objects:
                        for coll in list(camera_obj.users_collection):
                            coll.objects.unlink(camera_obj)
                        graph_collection.objects.link(camera_obj)

                # Re-evaluate animation end frame based on data, even if not rebuilding graph elements
                data_list, month_list, number_of_data = read_csv_data(CSV_FILE_PATH, DATA_COLUMN, MONTH_COLUMN)
                if number_of_data > 1:
                    anim_end_frame = GRAPH_ANIM_START_FRAME + GRAPH_ANIM_LENGTH_DATA * (number_of_data - 1)
                else:
                    anim_end_frame = GRAPH_ANIM_START_FRAME + GRAPH_ANIM_LENGTH_DATA
                
                setup_scene_settings(anim_end_frame)
                
                # Restore 3D cursor
                bpy.context.scene.cursor.location.xyz = self._saved_cursor_loc
                bpy.ops.object.select_all(action='DESELECT')
                print("\nGraph Animation script finished (skipped rebuild).")
                return {'FINISHED'}
            else:
                print_debug_info("Existing 'Graph_Elements' found. Clearing contents to rebuild or it's empty.")
                
                # CRITICAL: Never reset transformations for any object
                print_debug_info("Preserving all object transformations during rebuild")

                # Clear children of the master empty first
                for child in list(graph_master_empty.children):
                    # Only remove objects that belong to the GRAPH, not background
                    if child.name != "Graph_Camera" and not child.name.startswith("Background_"):
                        bpy.data.objects.remove(child, do_unlink=True)

                # Unlink objects from this collection and delete them
                for obj in list(graph_collection.objects):
                    # Preserve background objects by name check
                    if (obj.name != "Graph_Master" and 
                        obj.name != "Graph_Camera" and 
                        not obj.name.startswith("Background_")):
                        
                        graph_collection.objects.unlink(obj)
                        # If object has no other users, delete it
                        if not obj.users_collection:
                            bpy.data.objects.remove(obj, do_unlink=True)
        else:
            print_debug_info("No existing 'Graph_Elements' found. Creating new.")
            bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0,0,0))
            graph_master_empty = bpy.context.active_object
            graph_master_empty.name = "Graph_Master"

            graph_collection = bpy.data.collections.new("Graph_Elements")
            bpy.context.scene.collection.children.link(graph_collection)

        # Link graph master empty to its collection (ensure it's only in this one)
        for coll in list(graph_master_empty.users_collection):
            if coll != graph_collection:
                coll.objects.unlink(graph_master_empty)
        if graph_master_empty.name not in graph_collection.objects:
            graph_collection.objects.link(graph_master_empty)

        # 1. Read Data
        data_list, month_list, number_of_data = read_csv_data(CSV_FILE_PATH, DATA_COLUMN, MONTH_COLUMN)

        if number_of_data == 0:
            print("No valid data found in the CSV file. Exiting script gracefully.")
            self.report({'WARNING'}, "No valid data found in CSV. Graph not generated.")
            return {'CANCELLED'}

        # 2. Normalize Data
        display_data = normalize_and_display_data(data_list)

        # Calculate animation end frame based on data length
        if number_of_data > 1:
            anim_end_frame = GRAPH_ANIM_START_FRAME + GRAPH_ANIM_LENGTH_DATA * (number_of_data - 1)
        else:
            anim_end_frame = GRAPH_ANIM_START_FRAME + GRAPH_ANIM_LENGTH_DATA

        # 3. Setup Materials
        material_1, material_2, material_3, material_4 = setup_materials()

        # 4. Create Curve and Animated Object
        curve_path_obj, animated_obj = create_curve_and_animated_object(
            display_data, GRAPH_START_POSITION, GRAPH_X_AXIS_SPREAD,
            GRAPH_ANIM_START_FRAME, anim_end_frame, material_1,
            ANIMATED_OBJECT_TYPE, ANIMATED_OBJECT_NAME, ANIMATED_OBJECT_SCALE,
            graph_master_empty, graph_collection # Pass parent and collection
        )

        # 5. Create Data Points and Text
        create_data_points_and_text(data_list, month_list, display_data, 
                                    GRAPH_START_POSITION, GRAPH_X_AXIS_SPREAD, GRAPH_ANIM_START_FRAME, 
                                    GRAPH_ANIM_LENGTH_DATA, CURRENCY_SYMBOL, material_2,
                                    graph_master_empty, graph_collection) # Pass parent and collection

        # 7. Setup Camera Animation
        if curve_path_obj and animated_obj: 
            setup_camera_animation(curve_path_obj, animated_obj, 
                                   GRAPH_ANIM_START_FRAME, anim_end_frame, 
                                   number_of_data, GRAPH_X_AXIS_SPREAD,
                                   graph_collection) # Pass graph collection for camera
        else:
            print("Skipping camera animation: Curve object or animated object not found for graph.")

        # 8. Setup Scene Settings (This script manages global scene frames and render engine)
        setup_scene_settings(anim_end_frame)

        # Restore background collections to their original state
        for state in background_states:
            coll = bpy.data.collections.get(state["name"])
            if coll:
                coll.hide_viewport = state["hide_viewport"]
                coll.hide_render = state["hide_render"]
                
                # Ensure background objects remain in their collections
                for obj_name in state["objects"]:
                    obj = bpy.data.objects.get(obj_name)
                    if obj and obj.name not in coll.objects:
                        coll.objects.link(obj)
                        
                # Restore object transformations
                for obj_state in state["object_states"]:
                    obj = bpy.data.objects.get(obj_state["name"])
                    if obj:
                        try:
                            obj.location = obj_state["location"]
                            obj.rotation_euler = obj_state["rotation_euler"]
                            obj.scale = obj_state["scale"]
                        except Exception as e:
                            print(f"Error restoring state for {obj.name}: {e}")

        # Clean-up work
        bpy.context.scene.cursor.location.xyz = self._saved_cursor_loc # Restore 3D cursor
        bpy.ops.object.select_all(action='DESELECT') # Deselect all objects at the end

        print("\n3D Graph Animation generation complete. Check console for any errors.")
        print(f"Animation runs from frame {bpy.context.scene.frame_start} to {bpy.context.scene.frame_end}.")
        print("Please check the 'Graph_Elements' collection in your Blender Outliner.")

        return {'FINISHED'}

def register():
    bpy.utils.register_class(GraphAnimatorOperator)


def unregister():
    bpy.utils.unregister_class(GraphAnimatorOperator)


def main():
    """
    Main function to orchestrate the graph generation.
    Registers and runs the operator.
    """
    print("=" * 50)
    print("STARTING BLENDER GRAPH ANIMATOR SCRIPT")
    print("=" * 50)

    # Ensure the operator is registered before calling it
    try:
        bpy.utils.register_class(GraphAnimatorOperator)
    except ValueError:
        # Already registered, unregister and re-register to ensure latest version
        bpy.utils.unregister_class(GraphAnimatorOperator)
        bpy.utils.register_class(GraphAnimatorOperator)

    # Call the operator to start the process
    bpy.ops.object.graph_animator("EXEC_DEFAULT")  # Use EXEC_DEFAULT for non-modal


if __name__ == "__main__":
    main()