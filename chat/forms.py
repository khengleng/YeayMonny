from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

from .models import AssistantConfig


class OperatorAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="ឈ្មោះគណនី ឬអ៊ីមែល")

    def clean_username(self):
        raw_value = (self.cleaned_data.get("username") or "").strip()
        if "@" not in raw_value:
            return raw_value

        user_model = get_user_model()
        user = user_model.objects.filter(email__iexact=raw_value).first()
        return user.get_username() if user else raw_value


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
