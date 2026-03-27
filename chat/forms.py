from django import forms

from .models import AssistantConfig


class AssistantPromptForm(forms.ModelForm):
    class Meta:
        model = AssistantConfig
        fields = ["system_prompt"]
        widgets = {
            "system_prompt": forms.Textarea(attrs={"rows": 18}),
        }
        labels = {
            "system_prompt": "សារណែនាំសម្រាប់យាយមុន្នី (System Prompt)",
        }
        help_texts = {
            "system_prompt": "សូមសរសេរជាភាសាខ្មែរងាយៗ ដើម្បីអោយយាយឆ្លើយសាមញ្ញ និងកក់ក្តៅ។",
        }


class AssistantAdvancedSettingsForm(forms.ModelForm):
    class Meta:
        model = AssistantConfig
        fields = ["model_name", "temperature"]
        widgets = {
            "model_name": forms.TextInput(),
            "temperature": forms.NumberInput(attrs={"step": "0.1", "min": "0.0", "max": "2.0"}),
        }
        labels = {
            "model_name": "ម៉ូឌែល OpenAI",
            "temperature": "កម្រិតភាពច្នៃប្រឌិត (0.0 - 2.0)",
        }
        help_texts = {
            "model_name": "ឧ. gpt-4.1-mini",
            "temperature": "តម្លៃទាប = ឆ្លើយថេរជាងមុន, តម្លៃខ្ពស់ = ច្នៃប្រឌិតជាងមុន។",
        }
