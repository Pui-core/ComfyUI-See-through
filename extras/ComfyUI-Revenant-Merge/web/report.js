import { app } from '../../scripts/app.js';
import { ComfyWidgets } from '../../scripts/widgets.js';
app.registerExtension({
    name: 'Revenant.MergeReport',
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== 'RevenantMergeReport') return;
        const previous = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            previous?.apply(this, arguments);
            if (!this._reportWidget) {
                this._reportWidget = ComfyWidgets.STRING(this, 'report', ['STRING', {multiline: true}], app).widget;
                this._reportWidget.inputEl.readOnly = true;
                this._reportWidget.serialize = false;
            }
            this._reportWidget.value = (message.text || []).join('\n');
            this.setSize([Math.max(this.size[0], 440), Math.max(this.size[1], 320)]);
        };
    },
});
