from django import forms

from .models import AssistantConfig


class AssistantConfigForm(forms.ModelForm):
    class Meta:
        model = AssistantConfig
        fields = ["system_prompt", "model_name", "temperature"]
        widgets = {
            "system_prompt": forms.Textarea(attrs={"rows": 18}),
            "model_name": forms.TextInput(),
            "temperature": forms.NumberInput(attrs={"step": "0.1", "min": "0.0", "max": "2.0"}),
        }
