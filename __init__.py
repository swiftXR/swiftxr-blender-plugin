
import webbrowser
import json
import requests
import bpy
import time
import re

from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    IntProperty,
    FloatVectorProperty
)
from bpy_extras.io_utils import ExportHelper

bl_info = {
    "name": "SwiftXR (3D/AR/VR) Exporter",
    "author": "SwiftXR",
    "version": (1, 0, 3),
    "blender": (2, 80, 0),
    "location": "File > Export",
    "description": "Export and Share blender scenes to the web, in 3D, AR or VR",
    "doc_url": "https://guide.swiftxr.io/plugins/blender",
    "category": "Import-Export",
    "support": "COMMUNITY"
}


# Save the API key to the user preferences
def save_api_key(addon_name, swiftxr_api_key):
    preferences = bpy.context.preferences
    addon_prefs = preferences.addons[addon_name].preferences
    addon_prefs.swiftxr_api_key = swiftxr_api_key

# Get the API key from the user preferences
def get_api_key(addon_name):
    preferences = bpy.context.preferences
    addon_prefs = preferences.addons[addon_name].preferences
    return addon_prefs.swiftxr_api_key


def get_json_from_text(json_string):
    return json.loads(json_string)


def get_text_from_json(json_main):
    return json.dumps(json_main)

# Returns a safe text that can be used for a URL
def get_safe_text_input(unsafe_text):
    safe_text = re.sub(
        r'[^\w\d_-]', '', unsafe_text.lower().replace(" ", "-"))
    
    return safe_text

# Save the Export configuration, including SwiftXR Published project ID
def save_export_config(var_name, data):

    scene = bpy.context.scene

    swiftxr_data_block = scene.get(var_name)

    if not swiftxr_data_block:
        swiftxr_data_block = bpy.data.texts.new(var_name)
        scene[var_name] = swiftxr_data_block

    json_str = get_text_from_json(data)
    swiftxr_data_block.clear()
    swiftxr_data_block.write(json_str)


# Get the Export configuration, including SwiftXR Published project ID
def get_export_config(var_name):

    scene = bpy.context.scene

    swiftxr_data_block = scene.get(var_name)

    if not swiftxr_data_block:
        return {}

    try:
        config = swiftxr_data_block.as_string()
        return get_json_from_text(config)
    except:
        return {}

## Get color as string
def serialize_background_color(color):

    r, g, b = color
    r_hex = format(int(r * 255), '02x')
    g_hex = format(int(g * 255), '02x')
    b_hex = format(int(b * 255), '02x')

    # Create the hex color value by concatenating the components
    hex_color = '#' + r_hex + g_hex + b_hex

    return hex_color

class SwiftXRPopup(bpy.types.Operator):
    """A simple popup"""
    bl_idname = "swiftxr.popup"
    bl_label = "SwiftXR Notification"

    message: bpy.props.StringProperty()

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.label(text=self.message)

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


class SwiftXRConfirm(bpy.types.Operator):
    """Confirmation operator"""
    bl_idname = "swiftxr.confirm"
    bl_label = "Do you really want to do that?"
    bl_options = {'REGISTER', 'INTERNAL'}
    options = {'REGISTER', 'INTERNAL'}
    icon = 'QUESTION'

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        self.report({'INFO'}, "YES!")
        return {'FINISHED'}

    def invoke(self, context, event):

        return context.window_manager.invoke_confirm(self, event)


class SwiftXRGenerateAPIKey(bpy.types.Operator):
    """Generate API key for SwiftXR"""
    bl_idname = "swiftxr.generate_api_key"
    bl_label = "Generate API Key"

    generate_api_key_url = 'https://swiftxr.io/hub/settings#profile'

    def execute(self, context):
        # Call the API key generation function here
        webbrowser.open(self.generate_api_key_url)
        return {'FINISHED'}
    

class SwiftXRPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    swiftxr_api_key: bpy.props.StringProperty(
        name="SwiftXR API Key",
        description="API key for your SwiftXR account",
        default="",
    )

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "swiftxr_api_key")

        layout.label(
            text="The API key enables easy authorisation to use the SwiftXR Platform")
        
        # Add a button to generate the API key
        layout.operator("swiftxr.generate_api_key")


class SwiftXRExport(bpy.types.Operator, ExportHelper):
    """Export Blender Scene as GLB to SwiftXR"""
    bl_idname = "export.swiftxr"
    bl_label = "Export to SwiftXR"
    bl_options = {'UNDO', 'PRESET'}

    filename_ext = ".glb"
    filter_glob: StringProperty(default="*.glb", options={'HIDDEN'})

    swiftxr_site_name: StringProperty(
        name="Project Name",
        description="Name of the Website, this name will also be used to generate a URL",
        default="",
        maxlen=255,
    )

    use_selection: BoolProperty(
        name="Selected Objects",
        description="Export selected objects only",
        default=False,
    )

    use_visible: BoolProperty(
        name="Visible Objects",
        description="Export visible objects only",
        default=False,
    )

    use_active_collection: BoolProperty(
        name="Active Collection",
        description="Export only objects from the active collection (and its children)",
        default=False,
    )

    export_animations: BoolProperty(
        name="Animations",
        description="Exports active actions and tracks as glTF animations",
        default=False,
    )

    immersive_mode: EnumProperty(
        name="Mode",
        items=(('3d', "3D", "View in 3D on the Web"),
               ('model', "3D & Augmented Reality (AR)",
                "View in 3D on the Web and in AR"),
                # VR Mode - Coming Soon
                ('vr', "3D & Virtual Reality (VR)",
                "View in 3D on the Web and in VR")
               ),
        default='model'
    )

    background_color: FloatVectorProperty(
        name="Background Color",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0),  # Default white color
        min=0.0,
        max=1.0
    )

    auto_rotate: BoolProperty(
        name="Auto Rotate",
        description="Enable automatic rotation of the model on the web",
        default=True,
    )

    tooltip: StringProperty(
        name="Button Tooltip",
        description="Sets a trigger message to go into AR or VR",
        default="View in my Space",
        maxlen=255,
    )

    image_compression: IntProperty(
        name="Texture Compression Level",
        description="Controls texture compression level: 0 = no compression, 10 = max compression.",
        default=5,
        min=0,
        max=10
    )

    model_compression: IntProperty(
        name="Model Compression Level",
        description="Controls model compression level: 0 = no compression, 10 = max compression.",
        default=5,
        min=0,
        max=10
    )

    PLUGIN_BLOCK_NAME = "swiftxr_block"
    SWIFTXR_API_URL = "https://api.swiftxr.io/v1"

    def draw(self, context):
        swiftxr_api_key = get_api_key(__name__)

        if not swiftxr_api_key:
            # API key is not set, display a message to the user
            self.layout.label(
                text="API key not set. Please set your API key in the plugin preferences.")
            return
        
        self.layout.label(
            text="Creation: 1 credit per 1MB of export size. Updates: MB Diff between the old and new export sizes.",
            icon='INFO',
            translate=False)
        
        pass


    def execute(self, context):

        swiftxr_api_key = get_api_key(__name__)

        #result = bpy.ops.swiftxr.confirm('INVOKE_DEFAULT')

        if not swiftxr_api_key:
            bpy.ops.swiftxr.popup(
                'INVOKE_DEFAULT', message="API Key cannot be left blank.")
            #self.report({'ERROR'}, "API Key cannot be empty")
            return {'CANCELLED'}

        if not self.swiftxr_site_name:
            bpy.ops.swiftxr.popup(
                'INVOKE_DEFAULT', message="Project Name cannot be left blank")
            #self.report({'ERROR'}, "API Key cannot be empty")
            return {'CANCELLED'}

        # Export scene or selected object as GLTF 2.0
        bpy.ops.export_scene.gltf(
            filepath=self.filepath, check_existing=False, use_selection=self.use_selection, use_visible=self.use_visible, use_active_collection=self.use_active_collection, export_animations=self.export_animations)

        wm = bpy.context.window_manager
        wm.progress_begin(0, 100)

        self.report({'INFO'}, "Uploading file to SwiftXR...")

        # Set Request Header
        headers = {"Authorization": "Bearer " + swiftxr_api_key}

        # Set Request Body
        use_ar = self.immersive_mode == "AR"
        compress_model = self.model_compression != 0
        compress_image = self.image_compression != 0

        create_data = {
            "site_name": get_safe_text_input(self.swiftxr_site_name),
            "config": {
                "type": self.immersive_mode,
                "logo_url": "",
                "compress_model": compress_model,
                "model_compression_level": self.model_compression,
                "compress_image": compress_image,
                "image_compression_level": self.image_compression,
                "use_ar": use_ar,
                "tooltip": self.tooltip,
                "background": serialize_background_color(self.background_color),
                "auto_rotate": self.auto_rotate,
            }
        }

        # Get previous Stored Config
        config = get_export_config(self.PLUGIN_BLOCK_NAME)

        site_id = config.get("site_id")

        # Make request to SwiftXR API server
        if not site_id:
            state_create = requests.post(
                self.SWIFTXR_API_URL + "/sites/",
                headers=headers, 
                json=create_data)
        else:
            state_create = requests.patch(
                self.SWIFTXR_API_URL + "/sites/" + site_id,
                headers=headers, 
                json=create_data)

        wm.progress_update(25)

        # In case the project has been deleted on the platform, but the ID is still present in the scene, we check for "site not found" and create based on the name

        if state_create.status_code == 400 and site_id:
            try:
                message = json.loads(state_create.text)["error"]

                if message == "site not found":
                    state_create = requests.post(
                        self.SWIFTXR_API_URL + "/sites/",
                        headers=headers,
                        json=create_data)
            except:
                message = "Could not update project, kindly ocntact support or create a new blender scene"
                bpy.ops.swiftxr.popup(
                    'INVOKE_DEFAULT', message=message)
                return {'CANCELLED'}

        if state_create.status_code == 200:

            create_message = json.loads(state_create.text)["site"]

            save_export_config(self.PLUGIN_BLOCK_NAME, create_message)

            site_id = create_message.get("site_id")

            with open(self.filepath, "rb") as f:
                data = f.read()
                files = {'deploy': ('deploy.glb', data)}

            state_deploy = requests.post(
                self.SWIFTXR_API_URL + "/sites/deploy/" + site_id,
                headers=headers, 
                files=files)

            if state_deploy.status_code == 200:
                deploy_response = json.loads(state_deploy.text)["site"]
                site_url = deploy_response["site_url"]
                time.sleep(5)
                webbrowser.open(site_url)
                message = "Scene exported to SwiftXR successfully"
            else:
                try:
                    error_message = json.loads(state_deploy.text)

                    credits_error = error_message.get("error_credit")
                    default_error = config.get("error")
                    
                    if credits_error: 
                        message = credits_error
                    else:
                       message = default_error
                except:
                    message = "An error occurred while exporting scene to SwiftXR"
        else:
            try:
                message = json.loads(state_create.text)["error"]
            except:
                message = "An error occurred while exporting scene to SwiftXR"

        wm.progress_update(100)
        wm.progress_end()

        try:
            bpy.ops.swiftxr.popup(
                'INVOKE_DEFAULT', message=message)
            self.report({'INFO'}, message)
        except:
            message = "An error occurred while exporting scene to SwiftXR"
            bpy.ops.swiftxr.popup(
                'INVOKE_DEFAULT', message=message)
            self.report({'INFO'}, message)
        return {'FINISHED'}


class SWIFTXR_PT_export_main(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = ""
    bl_parent_id = "FILE_PT_operator"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "EXPORT_OT_swiftxr"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        sfile = context.space_data
        operator = sfile.active_operator

        row = layout.row(align=True)
        row.prop(operator, "swiftxr_site_name")
        row = layout.row(align=True)
        row.prop(operator, "immersive_mode")
        row = layout.row(align=True)
        row.prop(operator, "background_color")
        


class SWIFTXR_PT_export_include(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Include"
    bl_parent_id = "FILE_PT_operator"
    bl_default_closed = True

    @classmethod
    def poll(cls, context):

        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "EXPORT_OT_swiftxr"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        sfile = context.space_data
        operator = sfile.active_operator

        sublayout = layout.column(heading="Limit to")
        sublayout.prop(operator, "use_selection")
        sublayout.prop(operator, "use_visible")
        sublayout.prop(operator, "use_active_collection")
        sublayout.prop(operator, "export_animations")
        sublayout.prop(operator, "auto_rotate")
        sublayout.prop(operator, "tooltip")


class SWIFTXR_PT_export_compression(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Compression"
    bl_parent_id = "FILE_PT_operator"
    bl_default_closed = True

    @classmethod
    def poll(cls, context):

        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "EXPORT_OT_swiftxr"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        sfile = context.space_data
        operator = sfile.active_operator

        sublayout = layout.column(heading="3D Model Compression")
        sublayout.prop(operator, "image_compression")
        sublayout.prop(operator, "model_compression")


def menu_func_export(self, context):
    self.layout.operator(SwiftXRExport.bl_idname,
                         text="SwiftXR (3D/AR/VR) Viewer")


classes = (
    SwiftXRExport,
    SWIFTXR_PT_export_main,
    SWIFTXR_PT_export_include,
    SWIFTXR_PT_export_compression,
    SwiftXRPreferences,
    SwiftXRPopup,
    SwiftXRConfirm,
    SwiftXRGenerateAPIKey,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
