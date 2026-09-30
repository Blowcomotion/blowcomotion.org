from django import forms

from auction.models import normalize_phone


class BidderRegistrationForm(forms.Form):
    name = forms.CharField(max_length=255)
    email = forms.EmailField()
    phone = forms.CharField(
        max_length=30,
        help_text=(
            "Already registered on another device? Enter the same email and "
            "phone to continue bidding as the same person."
        ),
    )
    sms_opt_in = forms.BooleanField(
        required=False,
        label="Text me when I'm outbid (you can bid back by replying)",
    )
    accept_agreement = forms.BooleanField(
        required=False,
        label="I Accept the User Agreement",
        error_messages={"required": "Please accept the User Agreement to bid."},
    )

    def __init__(self, *args, require_agreement=False, **kwargs):
        super().__init__(*args, **kwargs)
        if require_agreement:
            self.fields["accept_agreement"].required = True
        else:
            del self.fields["accept_agreement"]

    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])


class MoneyField(forms.DecimalField):
    """Accepts "$1,000" as well as "1000"."""

    widget = forms.TextInput(attrs={"inputmode": "decimal"})

    def to_python(self, value):
        if isinstance(value, str):
            value = value.replace(",", "").replace("$", "").strip()
        return super().to_python(value)


class BidForm(forms.Form):
    amount = MoneyField(max_digits=8, decimal_places=2, min_value=0)
