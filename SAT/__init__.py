bl_info = {
    "name": "Sound Animation Tool",
    "blender": (4, 4, 0),
    "category": "Animation",
    "version": (1, 1, 0),
    "author": "MadPlix",
    "description": "Analyze audio tracks and automatically generate animations based on BPM or audio frequency energy – ideal for music visualizations, motion design, or reactive camera and light effects.",
}

import bpy
import os
import sys
import math

from bpy.props import StringProperty, IntProperty
from bpy.types import Operator, Panel, PropertyGroup
from bpy_extras.io_utils import ImportHelper
from bpy.props import EnumProperty
from bpy.path import abspath


addon_dir = os.path.dirname(__file__)
libs_dir = os.path.join(addon_dir, "libs")
if libs_dir not in sys.path:
    sys.path.append(libs_dir)

from .bpm_detect import detect_bpm
from . import freq_analysis


class BPMAddonProperties(bpy.types.PropertyGroup):

    audio_path: bpy.props.StringProperty(
        name="Audio File",
        description="Select a WAV or MP3 file",
        subtype='FILE_PATH'
    )

    def update_bpm(self, context):
        fps = context.scene.render.fps
        self.frames_per_beat = round((60 / self.bpm_value) * fps)
    
    bpm_value: bpy.props.IntProperty(
        name="BPM",
        description="Automatically detected or manually set BPM value",
        default=0,
        min=1,
        update=update_bpm
    )

    frames_per_beat: bpy.props.IntProperty(
        name="Frames per Beat",
        description="Distance between beats (in frames)",
        default=0
    )

    start_frame: bpy.props.IntProperty(
        name="Start Frame",
        description="First frame for the animation",
        default=1,
        min=1
    )

    end_frame: bpy.props.IntProperty(
        name="End Frame",
        description="Last frame for the animation",
        default=250,
        min=1
    )

    amplitude: bpy.props.FloatProperty(
        name="Amplitude",
        description="Strength of the animation impulse",
        default=1.0,
        min=0.0,
        soft_max=10.0
    )

    original_bpm: bpy.props.IntProperty(
        name="Original BPM",
        description="Initially detected BPM (stored internally)",
        default=0
    )

    transform_type: bpy.props.EnumProperty(
        name="Property",
        description="Which object property should be animated?",
        items=[
            ('location', "Location", ""),
            ('rotation_euler', "Rotation", ""),
            ('rotation_quaternion', "Rotation (Quaternion)", ""),
            ('scale', "Scale", "")
        ],
        default='location'
    )

    axes_xyz: bpy.props.EnumProperty(
        name="Axes",
        description="X/Y/Z axes",
        items=[
            ('X', "X", ""),
            ('Y', "Y", ""),
            ('Z', "Z", "")
        ],
        options={'ENUM_FLAG'},
        default={'Z'}
    )

    axes_wxyz: bpy.props.EnumProperty(
        name="Axes",
        description="W/X/Y/Z axes for quaternion rotation",
        items=[
            ('W', "W", ""),
            ('X', "X", ""),
            ('Y', "Y", ""),
            ('Z', "Z", "")
        ],
        options={'ENUM_FLAG'},
        default={'Z'}
    )

    def get_bone_items(self, context):
        obj = context.active_object
        if obj and obj.type == 'ARMATURE':
            return [(b.name, b.name, "") for b in obj.pose.bones]
        return []

    target_bone_name: bpy.props.EnumProperty(
        name="Bone",
        description="Select a bone (if Armature is active)",
        items=get_bone_items
    )

    impulse_type: bpy.props.EnumProperty(
        name="Impulse Shape",
        description="How each beat should be shaped in animation",
        items=[
            ('IMPULSE', "Impulse (default)", ""),
            ('SINUS', "Sinus Wave", ""),
            ('BOUNCE', "Bounce", ""),
            ('EASE', "Ease In/Out", "")
        ],
        default='IMPULSE'
    )

    motion_preset: bpy.props.EnumProperty(
        name="Preset",
        description="Predefined motion pattern",
        items=[
            ('NONE', "None", ""),
            ('SHAKE_X', "Shake (X)", ""),
            ('SHAKE_YZ', "Shake (Y + Z)", ""),
            ('PULSE_SCALE', "Pulse (Scale)", ""),
            ('ROTATE', "Wobble (Rotation)", "")
        ],
        default='NONE'
    )

    freq_band: bpy.props.EnumProperty(
        name="Frequency Band",
        description="Frequency range used for reactive animation",
        items=[
            ('NONE', "Select", "Please select a frequency band"),
            ('Sub-Bass', "Sub-Bass (20–60 Hz)", ""),
            ('Bass', "Bass (60 - 250 Hz)", ""),
            ('Low Midrange', "Low Midrange (250 – 500 Hz)", ""),
            ('Midrange', "Midrange (500 – 2k Hz)", ""),
            ('High Midrange', "High Midrange (2k – 4k Hz)", ""),
            ('Presence', "Presence (4k–6k Hz)", ""),
            ('Brilliance', "Brilliance (6k–20k Hz", "")
        ],
        default='NONE'
    )

class BPM_OT_AnalyzeFrequencies(bpy.types.Operator):
    bl_idname = "object.analyze_freq_energy"
    bl_label = "Analyze Frequencies"
    bl_description = "Perform a frequency analysis on the selected audio file and extract energy values per band"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.bpm_props
        filepath = abspath(props.audio_path)

        if not filepath.lower().endswith(".wav") or not os.path.isfile(filepath):
            self.report({'ERROR'}, "Invalid or missing WAV file.")
            return {'CANCELLED'}

        output_path = os.path.splitext(filepath)[0] + "_freq_data.json"
        try:
            freq_analysis.save_energy_as_json(filepath, output_path)
            self.report({'INFO'}, f"Frequency data saved to: {output_path}")
        except Exception as e:
            self.report({'ERROR'}, f"Analysis error: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}

class BPM_OT_ApplyFreqKeyframes(bpy.types.Operator):
    bl_idname = "object.apply_freq_keyframes"
    bl_label = "Apply Frequency Curve"
    bl_description = "Generate keyframes based on the selected frequency band of the audio file"
    bl_options = {'REGISTER'}

    def execute(self, context):
        import math
        import os
        props = context.scene.bpm_props
        obj = context.active_object

        if not obj:
            self.report({'WARNING'}, "No object selected.")
            return {'CANCELLED'}

        from bpy.path import abspath
        from .freq_analysis import analyze_frequency_bands

        filepath = abspath(props.audio_path)
        if not os.path.isfile(filepath):
            self.report({'ERROR'}, "Audio file not found.")
            return {'CANCELLED'}

        try:
            energy, duration, sr, hop = analyze_frequency_bands(filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Analysis failed: {e}")
            return {'CANCELLED'}

        band = props.freq_band
        values = energy.get(band)
        if not values:
            self.report({'ERROR'}, f"No data found for '{band}'.")
            return {'CANCELLED'}

        fps = sr / hop
        transform_type = props.transform_type

        # Achsenwahl
        if transform_type == 'rotation_quaternion':
            axes = props.axes_wxyz
            axis_map = {'W': 0, 'X': 1, 'Y': 2, 'Z': 3}
        else:
            axes = props.axes_xyz
            axis_map = {'X': 0, 'Y': 1, 'Z': 2}

        index = axis_map.get(list(axes)[0])

        # Zielobjekt vorbereiten (Bone oder Objekt)
        bone_name = props.target_bone_name
        use_bone = obj.type == 'ARMATURE' and bone_name and bone_name in obj.pose.bones
        target = obj.pose.bones[bone_name] if use_bone else obj

        # 🧠 Sicherstellen, dass rotation_mode mit transform_type übereinstimmt
        if hasattr(target, "rotation_mode"):
            if transform_type == 'rotation_quaternion' and target.rotation_mode != 'QUATERNION':
                target.rotation_mode = 'QUATERNION'
            elif transform_type == 'rotation_euler' and target.rotation_mode != 'XYZ':
                target.rotation_mode = 'XYZ'

        max_val = max(values) if max(values) > 0 else 1

        for i, raw in enumerate(values):
            norm_value = raw / max_val
            value = norm_value * props.amplitude
            frame = i * (context.scene.render.fps / fps)

            if transform_type == "location":
                target.location[index] = value
            elif transform_type == "rotation_euler":
                target.rotation_euler[index] = value
            elif transform_type == "rotation_quaternion":
                target.rotation_quaternion[index] = value
            elif transform_type == "scale":
                target.scale[index] = 1.0 + value

            if use_bone:
                data_path = f'pose.bones["{bone_name}"].{transform_type}'
            else:
                data_path = transform_type

            obj.keyframe_insert(data_path=data_path, index=index, frame=frame)

        # Interpolation verbessern
        if obj.animation_data and obj.animation_data.action:
            fcurve = obj.animation_data.action.fcurves.find(transform_type, index=index)
            if fcurve:
                for kp in fcurve.keyframe_points:
                    kp.handle_left_type = 'AUTO_CLAMPED'
                    kp.handle_right_type = 'AUTO_CLAMPED'

        self.report({'INFO'}, f"{len(values)} keyframes added from frequency band '{band}'.")
        return {'FINISHED'}

class BPM_OT_AnalyzeAudio(bpy.types.Operator):
    bl_idname = "object.bpm_analyze"
    bl_label = "Analyze BPM"
    bl_description = "Analyze the selected audio file and estimate the BPM (beats per minute)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.bpm_props
        filepath = abspath(props.audio_path)
        bpm = detect_bpm(filepath)

        if bpm:
            bpm = math.ceil(bpm)
            props.bpm_value = bpm
            props.original_bpm = bpm

            fps = context.scene.render.fps
            frames_per_beat = (60 / bpm) * fps
            props.frames_per_beat = round(frames_per_beat)

            self.report({'INFO'}, f"BPM: {bpm} → approx. {round(frames_per_beat)} frames per beat")
        else:
            props.bpm_value = 0
            props.frames_per_beat = 0
            self.report({'WARNING'}, "No BPM detected.")

        return {'FINISHED'}

class BPM_OT_HalveBPM(bpy.types.Operator):
    bl_idname = "object.bpm_halve"
    bl_label = "BPM halbieren"
    bl_description = "Divide the current BPM value in half for slower beat syncing"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.bpm_props
        if props.bpm_value > 1:
            props.bpm_value = max(1, props.bpm_value // 2)
            fps = context.scene.render.fps
            props.frames_per_beat = round((60 / props.bpm_value) * fps)
            self.report({'INFO'}, f"BPM halved: {props.bpm_value}")
        return {'FINISHED'}


class BPM_OT_DoubleBPM(bpy.types.Operator):
    bl_idname = "object.bpm_double"
    bl_label = "Double BPM"
    bl_description = "Double the current BPM value for faster beat syncing"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.bpm_props
        props.bpm_value *= 2
        fps = context.scene.render.fps
        props.frames_per_beat = round((60 / props.bpm_value) * fps)
        self.report({'INFO'}, f"BPM doubled: {props.bpm_value}")
        return {'FINISHED'}

class BPM_OT_ResetBPM(bpy.types.Operator):
    bl_idname = "object.bpm_reset"
    bl_label = "Reset BPM"
    bl_description = "Restore the BPM value to the originally detected value"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.bpm_props
        if props.original_bpm > 0:
            props.bpm_value = props.original_bpm
            fps = context.scene.render.fps
            props.frames_per_beat = round((60 / props.bpm_value) * fps)
            self.report({'INFO'}, f"BPM reset to: {props.bpm_value}")
        return {'FINISHED'}

class BPM_OT_ApplyBeatKeyframes(bpy.types.Operator):
    bl_idname = "object.apply_beat_keyframes"
    bl_label = "Generate BPM Curve"
    bl_description = "Generate animated F-Curves based on BPM, amplitude, and selected impulse shape"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.bpm_props
        obj = context.active_object

        if not obj:
            self.report({'WARNING'}, "No object selected.")
            return {'CANCELLED'}

        transform_type = props.transform_type
        bone_name = props.target_bone_name
        use_bone = obj.type == 'ARMATURE' and bone_name and bone_name in obj.pose.bones
        target = obj.pose.bones[bone_name] if use_bone else obj

        # 🧠 Set rotation_mode if needed
        if hasattr(target, "rotation_mode"):
            if transform_type == 'rotation_quaternion' and target.rotation_mode != 'QUATERNION':
                target.rotation_mode = 'QUATERNION'
            elif transform_type == 'rotation_euler' and target.rotation_mode != 'XYZ':
                target.rotation_mode = 'XYZ'

        # Motion preset
        preset = props.motion_preset
        if preset != 'NONE':
            start = props.start_frame
            end = props.end_frame

            if preset == 'SHAKE_X':
                for f in range(start, end + 1, 2):
                    obj.location.x = (-1)**f * 0.1
                    obj.keyframe_insert(data_path="location", index=0, frame=f)

            elif preset == 'SHAKE_YZ':
                for f in range(start, end + 1, 3):
                    obj.location.y = (-1)**f * 0.1
                    obj.location.z = (-1)**(f + 1) * 0.1
                    obj.keyframe_insert(data_path="location", index=1, frame=f)
                    obj.keyframe_insert(data_path="location", index=2, frame=f)

            elif preset == 'PULSE_SCALE':
                for f in range(start, end + 1, 8):
                    obj.scale = (1.3, 1.3, 1.3)
                    obj.keyframe_insert(data_path="scale", frame=f)
                    obj.scale = (1.0, 1.0, 1.0)
                    obj.keyframe_insert(data_path="scale", frame=f + 2)

            elif preset == 'ROTATE':
                for f in range(start, end + 1, 5):
                    if transform_type == 'rotation_quaternion':
                        obj.rotation_quaternion[3] = (-1)**f * 0.1
                        obj.keyframe_insert(data_path="rotation_quaternion", index=3, frame=f)
                    else:
                        obj.rotation_euler.z = (-1)**f * 0.1
                        obj.keyframe_insert(data_path="rotation_euler", index=2, frame=f)

            self.report({'INFO'}, f"Preset '{preset}' applied.")
            return {'FINISHED'}

        bpm = props.bpm_value
        frames_per_beat = props.frames_per_beat
        if bpm <= 0 or frames_per_beat <= 0:
            self.report({'WARNING'}, "Invalid BPM data.")
            return {'CANCELLED'}

        # Achsenwahl
        if transform_type == 'rotation_quaternion':
            axes = props.axes_wxyz
            axis_map = {'W': 0, 'X': 1, 'Y': 2, 'Z': 3}
        else:
            axes = props.axes_xyz
            axis_map = {'X': 0, 'Y': 1, 'Z': 2}

        fcurve_owner = obj
        if not fcurve_owner.animation_data:
            fcurve_owner.animation_data_create()
        if not fcurve_owner.animation_data.action:
            fcurve_owner.animation_data.action = bpy.data.actions.new(name="BPM_Action")

        for axis in axes:
            index = axis_map[axis]
            frame = props.start_frame
            end = props.end_frame

            while frame + 1 <= end:
                impulse = props.impulse_type

                def set_value(val):
                    if transform_type == 'location':
                        target.location[index] = val
                    elif transform_type == 'rotation_euler':
                        target.rotation_euler[index] = val
                    elif transform_type == 'rotation_quaternion':
                        target.rotation_quaternion[index] = val
                    elif transform_type == 'scale':
                        target.scale[index] = val

                if impulse == 'IMPULSE':
                    set_value(0.0)
                    target.keyframe_insert(data_path=transform_type, index=index, frame=frame)
                    set_value(props.amplitude)
                    target.keyframe_insert(data_path=transform_type, index=index, frame=frame + 0.015)

                elif impulse == 'SINUS':
                    import math
                    steps = 5
                    for i in range(steps + 1):
                        t = i / steps
                        value = math.sin(t * math.pi) * props.amplitude
                        current_frame = frame + t * frames_per_beat
                        set_value(value)
                        target.keyframe_insert(data_path=transform_type, index=index, frame=current_frame)

                elif impulse == 'BOUNCE':
                    bounce = [props.amplitude, -props.amplitude * 0.5, props.amplitude * 0.25, 0]
                    for i, val in enumerate(bounce):
                        current_frame = frame + i * (frames_per_beat / len(bounce))
                        set_value(val)
                        target.keyframe_insert(data_path=transform_type, index=index, frame=current_frame)

                elif impulse == 'EASE':
                    set_value(0.0)
                    target.keyframe_insert(data_path=transform_type, index=index, frame=frame)
                    set_value(props.amplitude)
                    target.keyframe_insert(data_path=transform_type, index=index, frame=frame + frames_per_beat)

                frame += frames_per_beat

        self.report({'INFO'}, f"Keyframes applied on {transform_type} ({', '.join(axes)})")
        return {'FINISHED'}

class BPM_PT_Main(bpy.types.Panel):
    bl_label = "Audio File"
    bl_idname = "BPM_PT_Main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SAT'

    def draw(self, context):
        layout = self.layout
        props = context.scene.bpm_props

        layout.label(text="Select an audio file (.wav or .mp3)") 
        layout.prop(props, "audio_path")

class BPM_PT_CurveSettings(bpy.types.Panel):
    bl_label = "Curve Settings"
    bl_idname = "BPM_PT_CurveSettings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SAT'

    def draw(self, context):
        layout = self.layout
        props = context.scene.bpm_props

        layout.prop(props, "start_frame", text="Start Frame")
        layout.prop(props, "end_frame", text="End Frame")
        layout.prop(props, "amplitude", text="Amplitude")

class BPM_PT_ObjectPanel(bpy.types.Panel):
    bl_label = "Target Object"
    bl_idname = "BPM_PT_ObjectPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SAT'

    def draw(self, context):
        layout = self.layout
        props = context.scene.bpm_props
        obj = context.active_object

        if obj:
            layout.label(text=f"Active Object: {obj.name}", icon='OBJECT_DATA')
            layout.label(text=f"Type: {obj.type}")
            if obj.type == 'ARMATURE':
                layout.prop(props, "target_bone_name", text="Bone")
        else:
            layout.label(text="⚠ No object selected", icon='ERROR')

        layout.separator()
        
        layout.prop(props, "transform_type", text="Property")
        if props.transform_type == 'rotation_quaternion':
            layout.prop(props, "axes_wxyz", expand=True, text="Axes (WXYZ)")
        else:
            layout.prop(props, "axes_xyz", expand=True, text="Axes (XYZ)")



class BPM_PT_BPMPanel(bpy.types.Panel):
    bl_label = "BPM Animation"
    bl_idname = "BPM_PT_BPMPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SAT'

    def draw(self, context):
        layout = self.layout
        props = context.scene.bpm_props

        layout.operator("object.bpm_analyze", text="Analyze BPM")
        layout.prop(props, "bpm_value", text="BPM")
        layout.label(text=f"Frames per Beat: {props.frames_per_beat}")
        row = layout.row(align=True)
        row.operator("object.bpm_halve", text="½ BPM")
        row.operator("object.bpm_double", text="×2 BPM")
        layout.operator("object.bpm_reset", text="Reset BPM")
        layout.separator()

        layout.prop(props, "impulse_type", text="Impulse Shape")
        layout.prop(props, "motion_preset", text="Preset")
        layout.separator()

        layout.operator("object.apply_beat_keyframes", text="Generate BPM Curve")

class BPM_PT_FreqPanel(bpy.types.Panel):
    bl_label = "Frequency Animation"
    bl_idname = "BPM_PT_FreqPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SAT'

    def draw(self, context):
        layout = self.layout
        props = context.scene.bpm_props

        layout.prop(props, "freq_band", text="Frequency Band")
        layout.operator("object.analyze_freq_energy", text="Analyze Frequencies")
        layout.operator("object.apply_freq_keyframes", text="Generate Frequency Curve")

classes = [
            BPMAddonProperties, BPM_OT_AnalyzeAudio, BPM_OT_ApplyBeatKeyframes, BPM_OT_HalveBPM, 
            BPM_OT_DoubleBPM, BPM_OT_ResetBPM, BPM_OT_AnalyzeFrequencies, BPM_OT_ApplyFreqKeyframes,
            BPM_PT_Main, BPM_PT_CurveSettings, BPM_PT_ObjectPanel, BPM_PT_FreqPanel, BPM_PT_BPMPanel
        ]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bpm_props = bpy.props.PointerProperty(type=BPMAddonProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.bpm_props

if __name__ == "__main__":
    register()
