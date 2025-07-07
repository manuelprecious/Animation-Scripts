import bpy

def export_background_objects(collection_name="BackgroundAssets"):
    output_lines = []

    for obj in bpy.data.collections[collection_name].all_objects:
        if obj.type == 'MESH':
            loc = obj.matrix_world.translation
            rot = obj.rotation_euler
            scale = obj.scale
            mesh_name = obj.data.name
            obj_name = obj.name

            code = f"""
# Create object: {obj_name}
mesh = bpy.data.meshes.get("{mesh_name}")
if mesh:
    obj = bpy.data.objects.new("{obj_name}", mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = ({loc.x:.4f}, {loc.y:.4f}, {loc.z:.4f})
    obj.rotation_euler = ({rot.x:.4f}, {rot.y:.4f}, {rot.z:.4f})
    obj.scale = ({scale.x:.4f}, {scale.y:.4f}, {scale.z:.4f})
"""
            output_lines.append(code)

    with open(bpy.path.abspath("//background_export.py"), 'w') as f:
        f.write("# Auto-generated background script\n")
        f.write("\n".join(output_lines))

export_background_objects()
