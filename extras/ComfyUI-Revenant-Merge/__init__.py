"""Optional saved-parts merge nodes; no diffusion model required."""
from pathlib import Path
import folder_paths
import torch
from .parts_io import read_parts, merge_parts, preview, inventory


class RevenantLoadSavedParts:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'layers_json': ('STRING', {'default': '', 'multiline': False})}}
    RETURN_TYPES = ('SEETHROUGH_PARTS', 'IMAGE', 'STRING')
    RETURN_NAMES = ('parts', 'preview', 'part_names')
    FUNCTION = 'load'
    CATEGORY = 'SeeThrough/Merge'

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # PNGs may be modified while the manifest path stays unchanged.
        return float('nan')

    def load(self, layers_json):
        if not layers_json.strip():
            raise ValueError('Choose the *_layers.json saved by SeeThrough SavePSD, not a PSD file.')
        path = Path(layers_json.strip().strip('"'))
        if not path.is_absolute():
            path = Path(folder_paths.get_output_directory()) / path
        parts = read_parts(path)
        return parts, torch.from_numpy(preview(parts)).unsqueeze(0), inventory(parts)


class RevenantMergeSavedParts:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'original': ('SEETHROUGH_PARTS',), 'underlay': ('SEETHROUGH_PARTS',),
            'replace_parts': ('STRING', {'default': 'neck\ntopwear', 'multiline': True}),
            'remove_parts': ('STRING', {'default': '', 'multiline': True}),
            'offset_x': ('INT', {'default': 0, 'min': -16384, 'max': 16384}),
            'offset_y': ('INT', {'default': 0, 'min': -16384, 'max': 16384}),
        }}
    RETURN_TYPES = ('SEETHROUGH_PARTS', 'IMAGE', 'STRING')
    RETURN_NAMES = ('parts', 'preview', 'report')
    FUNCTION = 'merge'
    CATEGORY = 'SeeThrough/Merge'

    def merge(self, original, underlay, replace_parts, remove_parts, offset_x, offset_y):
        parts = merge_parts(original, underlay, replace_parts, remove_parts, offset_x, offset_y)
        report = f'Replaced: {replace_parts}\nRemoved: {remove_parts}\nOffset: {offset_x}, {offset_y}\n\nOriginal:\n{inventory(original)}\n\nUnderlay:\n{inventory(underlay)}\n\nMerged:\n{inventory(parts)}'
        return parts, torch.from_numpy(preview(parts)).unsqueeze(0), report


class RevenantMergeReport:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'text': ('STRING', {'forceInput': True})}}
    RETURN_TYPES = ()
    FUNCTION = 'show'
    CATEGORY = 'SeeThrough/Merge'
    OUTPUT_NODE = True

    def show(self, text):
        return {'ui': {'text': [text]}}


WEB_DIRECTORY = './web'
NODE_CLASS_MAPPINGS = {c.__name__: c for c in [RevenantLoadSavedParts, RevenantMergeSavedParts, RevenantMergeReport]}
NODE_DISPLAY_NAME_MAPPINGS = {'RevenantLoadSavedParts': 'SeeThrough Load Saved Parts', 'RevenantMergeSavedParts': 'SeeThrough Merge Selected Parts', 'RevenantMergeReport': 'SeeThrough Part Names / Report'}
