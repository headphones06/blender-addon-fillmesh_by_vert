'''
変更点は日本語でコメントを記述しています。
'''

import bmesh
import bpy
import itertools
import mathutils
import math
from mathutils import Vector
from bpy_extras import view3d_utils

bl_info = {
    "name": "Fill mesh by vert",
    "author": "Takigami Ryota",
    "version": (0, 1, 0),
    "blender": (3, 1, 2),
    "location": "View3D > Sidebar",
    "description": "アドオン「F2」を頂点のみに変更し、実行をSidebarでのボタンクリックに変更",
    "support": 'TESTING',
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}


#編集モード限定で、Sidebarに実行タブを呼び出すクラスを作成。
class Practice_MenuTabAdd(bpy.types.Panel):
    
    bl_label = "Vertex_print"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fill mesh"
    bl_context = "mesh_edit"
    
    @classmethod
    def poll(cls, context):
        # オブジェクトが選択されているときのみパネルを表示させる
        for o in bpy.data.objects:
            if o.select_get():
                return True
        return False
    
    #実行用のボタンを作成する。
    def draw(self, context):
        layout = self.layout
        layout.row().operator(Vertex_F2.bl_idname)


# copied from "mesh_f2.py"
def get_uv_layer(ob, bm, mat_index):
    uv = None
    uv_layer = None
    if ob.material_slots:
        me = ob.data
        if me.uv_layers:
            uv = me.uv_layers.active.name
    # 'material_slots' is deprecated (Blender Internal)
    # else:
    #     mat = ob.material_slots[mat_index].material
    #     if mat is not None:
    #         slot = mat.texture_slots[mat.active_texture_index]
    #         if slot and slot.uv_layer:
    #             uv = slot.uv_layer
    #         else:
    #             for tex_slot in mat.texture_slots:
    #                 if tex_slot and tex_slot.uv_layer:
    #                     uv = tex_slot.uv_layer
    #                     break
    if uv:
        uv_layer = bm.loops.layers.uv.get(uv)

    return (uv_layer)


# copied from "mesh_f2.py"
def quad_from_vertex(bm, vert_sel, context, event):
    addon_prefs = context.preferences.addons[__name__].preferences
    ob = context.active_object
    me = ob.data
    region = context.region
    region_3d = context.space_data.region_3d

    # find linked edges that are open (<2 faces connected)
    edges = [edge for edge in vert_sel.link_edges if len(edge.link_faces) < 2]
    if len(edges) < 2:
        return

    # determine which edges to use, based on mouse cursor position
    min_dist = False
    mouse_pos = mathutils.Vector([event.mouse_region_x, event.mouse_region_y])
    for a, b in itertools.combinations(edges, 2):
        other_verts = [vert for edge in [a, b] for vert in edge.verts \
                       if not vert.select]
        mid_other = (other_verts[0].co.copy() + other_verts[1].co.copy()) \
                    / 2
        new_pos = 2 * (mid_other - vert_sel.co.copy()) + vert_sel.co.copy()
        world_pos = ob.matrix_world @ new_pos
        screen_pos = view3d_utils.location_3d_to_region_2d(region, region_3d,
                                                           world_pos)
        dist = (mouse_pos - screen_pos).length
        if not min_dist or dist < min_dist[0]:
            min_dist = (dist, (a, b), other_verts, new_pos)

    # create vertex at location mirrored in the line, connecting the open edges
    edges = min_dist[1]
    other_verts = min_dist[2]
    new_pos = min_dist[3]
    vert_new = bm.verts.new(new_pos)

    # normal detection
    flip_align = True
    normal_edge = edges[0]
    if not normal_edge.link_faces:
        normal_edge = edges[1]
        if not normal_edge.link_faces:
            # no connected faces, so no need to flip the face normal
            flip_align = False
    if flip_align:  # there is a face to which the normal can be aligned
        ref_verts = [v for v in normal_edge.link_faces[0].verts]
        if other_verts[0] in ref_verts:
            va_1 = other_verts[0]
            va_2 = vert_sel
        else:
            va_1 = vert_sel
            va_2 = other_verts[1]
        if (va_1 == ref_verts[0] and va_2 == ref_verts[-1]) or \
                (va_2 == ref_verts[0] and va_1 == ref_verts[-1]):
            # reference verts are at start and end of the list -> shift list
            ref_verts = ref_verts[1:] + [ref_verts[0]]
        if ref_verts.index(va_1) > ref_verts.index(va_2):
            # connected face has same normal direction, so don't flip
            flip_align = False

    # material index detection
    ref_faces = vert_sel.link_faces
    if not ref_faces:
        mat_index = False
        smooth = False
    else:
        mat_index = ref_faces[0].material_index
        smooth = ref_faces[0].smooth

    if addon_prefs.quad_from_v_mat:
        mat_index = bpy.context.object.active_material_index

    # create face between all 4 vertices involved
    verts = [other_verts[0], vert_sel, other_verts[1], vert_new]
    if flip_align:
        verts.reverse()
    face = bm.faces.new(verts)
    if mat_index:
        face.material_index = mat_index
    face.smooth = smooth

    # change selection
    vert_new.select = True
    vert_sel.select = False

    # adjust uv-map
    if __name__ != '__main__':
        if addon_prefs.adjustuv:
            uv_layer = get_uv_layer(ob, bm, mat_index)
            if uv_layer:
                uv_others = {}
                uv_sel = None
                uv_new = None
                # get original uv coordinates
                for i in range(2):
                    for loop in other_verts[i].link_loops:
                        if loop.face.index > -1:
                            uv_others[loop.vert.index] = loop[uv_layer].uv
                            break
                if len(uv_others) == 2:
                    mid_other = (list(uv_others.values())[0] +
                                 list(uv_others.values())[1]) / 2
                    for loop in vert_sel.link_loops:
                        if loop.face.index > -1:
                            uv_sel = loop[uv_layer].uv
                            break
                    if uv_sel:
                        uv_new = 2 * (mid_other - uv_sel) + uv_sel

                # set uv coordinates for new loops
                if uv_new:
                    for loop in face.loops:
                        if loop.vert.index == -1:
                            x, y = uv_new
                        elif loop.vert.index in uv_others:
                            x, y = uv_others[loop.vert.index]
                        else:
                            x, y = uv_sel
                        loop[uv_layer].uv = (x, y)

    # toggle mode, to force correct drawing
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='EDIT')

# copied from "mesh_f2.py"
def expand_vert(self, context, event):
    addon_prefs = context.preferences.addons[__name__].preferences
    ob = context.active_object
    obj = bpy.context.object
    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    region = context.region
    region_3d = context.space_data.region_3d
    rv3d = context.space_data.region_3d

    for v in bm.verts:
        if v.select:
            v_active = v

    try:
        depth_location = v_active.co
    except:
        return {'CANCELLED'}
    # create vert in mouse cursor location

    mouse_pos = Vector((event.mouse_region_x, event.mouse_region_y))
    location_3d = view3d_utils.region_2d_to_location_3d(region, rv3d, mouse_pos, depth_location)

    c_verts = []
    # find and select linked edges that are open (<2 faces connected) add those edge verts to c_verts list
    linked = v_active.link_edges
    for edges in linked:
        if len(edges.link_faces) < 2:
            edges.select = True
            for v in edges.verts:
                if v is not v_active:
                    c_verts.append(v)

    # Compare distance in 2d between mouse and edges middle points
    screen_pos_va = view3d_utils.location_3d_to_region_2d(region, region_3d,
                                                          ob.matrix_world @ v_active.co)
    screen_pos_v1 = view3d_utils.location_3d_to_region_2d(region, region_3d,
                                                          ob.matrix_world @ c_verts[0].co)
    screen_pos_v2 = view3d_utils.location_3d_to_region_2d(region, region_3d,
                                                          ob.matrix_world @ c_verts[1].co)

    mid_pos_v1 = Vector(((screen_pos_va[0] + screen_pos_v1[0]) / 2, (screen_pos_va[1] + screen_pos_v1[1]) / 2))
    mid_pos_V2 = Vector(((screen_pos_va[0] + screen_pos_v2[0]) / 2, (screen_pos_va[1] + screen_pos_v2[1]) / 2))

    dist1 = math.log10(pow((mid_pos_v1[0] - mouse_pos[0]), 2) + pow((mid_pos_v1[1] - mouse_pos[1]), 2))
    dist2 = math.log10(pow((mid_pos_V2[0] - mouse_pos[0]), 2) + pow((mid_pos_V2[1] - mouse_pos[1]), 2))

    bm.normal_update()
    bm.verts.ensure_lookup_table()

    # Deselect not needed point and create new face
    if dist1 < dist2:
        c_verts[1].select = False
        lleft = c_verts[0].link_faces

    else:
        c_verts[0].select = False
        lleft = c_verts[1].link_faces

    lactive = v_active.link_faces
    # lverts = lactive[0].verts

    mat_index = lactive[0].material_index
    smooth = lactive[0].smooth

    for faces in lactive:
        if faces in lleft:
            cface = faces
            if len(faces.verts) == 3:
                bm.normal_update()
                bmesh.update_edit_mesh(obj.data)
                bpy.ops.mesh.select_all(action='DESELECT')
                v_active.select = True
                bpy.ops.mesh.rip_edge_move('INVOKE_DEFAULT')
                return {'FINISHED'}

    lverts = cface.verts

    # create triangle with correct normal orientation
    # if You looking at that part - yeah... I know. I still dont get how blender calculates normals...

    # from L to R
    if dist1 < dist2:
        if (lverts[0] == v_active and lverts[3] == c_verts[0]) \
                or (lverts[2] == v_active and lverts[1] == c_verts[0]) \
                or (lverts[1] == v_active and lverts[0] == c_verts[0]) \
                or (lverts[3] == v_active and lverts[2] == c_verts[0]):
            v_new = bm.verts.new(v_active.co)
            face_new = bm.faces.new((c_verts[0], v_new, v_active))

        elif (lverts[1] == v_active and lverts[2] == c_verts[0]) \
                or (lverts[0] == v_active and lverts[1] == c_verts[0]) \
                or (lverts[3] == v_active and lverts[0] == c_verts[0]) \
                or (lverts[2] == v_active and lverts[3] == c_verts[0]):
            v_new = bm.verts.new(v_active.co)
            face_new = bm.faces.new((v_active, v_new, c_verts[0]))

        else:
            pass
    # from R to L
    else:
        if (lverts[2] == v_active and lverts[3] == c_verts[1]) \
                or (lverts[0] == v_active and lverts[1] == c_verts[1]) \
                or (lverts[1] == v_active and lverts[2] == c_verts[1]) \
                or (lverts[3] == v_active and lverts[0] == c_verts[1]):
            v_new = bm.verts.new(v_active.co)
            face_new = bm.faces.new((v_active, v_new, c_verts[1]))

        elif (lverts[0] == v_active and lverts[3] == c_verts[1]) \
                or (lverts[2] == v_active and lverts[1] == c_verts[1]) \
                or (lverts[1] == v_active and lverts[0] == c_verts[1]) \
                or (lverts[3] == v_active and lverts[2] == c_verts[1]):
            v_new = bm.verts.new(v_active.co)
            face_new = bm.faces.new((c_verts[1], v_new, v_active))

        else:
            pass

    # set smooth and mat based on starting face
    if addon_prefs.tris_from_v_mat:
        face_new.material_index = bpy.context.object.active_material_index
    else:
        face_new.material_index = mat_index
    face_new.smooth = smooth

    # update normals
    bpy.ops.mesh.select_all(action='DESELECT')
    v_new.select = True
    bm.select_history.add(v_new)

    bm.normal_update()
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.transform.translate('INVOKE_DEFAULT')


# copied from "mesh_f2.py"
def checkforconnected(connection):
    obj = bpy.context.object
    me = obj.data
    bm = bmesh.from_edit_mesh(me)

    # Checks for number of edes or faces connected to selected vertex
    for v in bm.verts:
        if v.select:
            v_active = v
    if connection == 'faces':
        linked = v_active.link_faces
    elif connection == 'edges':
        linked = v_active.link_edges

    bmesh.update_edit_mesh(obj.data)
    return len(linked)


# copied from "mesh_f2.py"
class F2AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    adjustuv : bpy.props.BoolProperty(
        name="Adjust UV",
        description="Automatically update UV unwrapping",
        default=False)
    autograb : bpy.props.BoolProperty(
        name="Auto Grab",
        description="Automatically puts a newly created vertex in grab mode",
        default=True)
    extendvert : bpy.props.BoolProperty(
        name="Enable Extend Vert",
        description="Enables a way to build tris and quads by adding verts",
        default=False)
    quad_from_e_mat : bpy.props.BoolProperty(
        name="Quad From Edge",
        description="Use active material for created face instead of close one",
        default=True)
    quad_from_v_mat : bpy.props.BoolProperty(
        name="Quad From Vert",
        description="Use active material for created face instead of close one",
        default=True)
    tris_from_v_mat : bpy.props.BoolProperty(
        name="Tris From Vert",
        description="Use active material for created face instead of close one",
        default=True)
    ngons_v_mat : bpy.props.BoolProperty(
        name="Ngons",
        description="Use active material for created face instead of close one",
        default=True)

    def draw(self, context):
        layout = self.layout

        col = layout.column()
        col.label(text="behaviours:")
        col.prop(self, "autograb")
        col.prop(self, "adjustuv")
        col.prop(self, "extendvert")

        col = layout.column()
        col.label(text="use active material when creating:")
        col.prop(self, "quad_from_e_mat")
        col.prop(self, "quad_from_v_mat")
        col.prop(self, "tris_from_v_mat")
        col.prop(self, "ngons_v_mat")


#記述箇所あり
class Vertex_F2(bpy.types.Operator):
    bl_idname = "mesh.f2_vertex"
    bl_label = "fill mesh by vertex"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    def usequad(self, bm, sel, context, event):
        quad_from_vertex(bm, sel, context, event)
        if __name__ != '__main__':
            addon_prefs = context.preferences.addons[__name__].preferences
            if addon_prefs.autograb:
                bpy.ops.transform.translate('INVOKE_DEFAULT')

    def invoke(self, context, event):
        bm = bmesh.from_edit_mesh(context.active_object.data)
        sel = [v for v in bm.verts if v.select]
        
        #頂点のみの参照なので、if条件を " 2 → 1 " に変更
        if len(sel) > 1:
            # original 'Make Edge/Face' behaviour
            try:
                bpy.ops.mesh.edge_face_add('INVOKE_DEFAULT')
                addon_prefs = context.preferences.addons[__name__].preferences
                if addon_prefs.ngons_v_mat:
                    bpy.ops.object.material_slot_assign()
            except:
                return {'CANCELLED'}
        elif len(sel) == 1:
            # single vertex selected -> mirror vertex and create new face
            addon_prefs = context.preferences.addons[__name__].preferences
            if addon_prefs.extendvert:
                if checkforconnected('faces') in [2]:
                    if checkforconnected('edges') in [3]:
                        expand_vert(self, context, event)
                    else:
                        self.usequad(bm, sel[0], context, event)
                elif checkforconnected('faces') in [1]:
                    if checkforconnected('edges') in [2]:
                        expand_vert(self, context, event)
                    else:
                        self.usequad(bm, sel[0], context, event)
                else:
                    self.usequad(bm, sel[0], context, event)
            else:
                self.usequad(bm, sel[0], context, event)

        #作成した頂点と重複する頂点があれば、マージする。
        bpy.ops.mesh.remove_doubles(threshold=0.0001, use_unselected=True)
        
        return {'FINISHED'}
        

classes = [Vertex_F2, F2AddonPreferences, Practice_MenuTabAdd]


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()


