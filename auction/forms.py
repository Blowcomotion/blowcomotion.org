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

    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])


class BidForm(forms.Form):
    amount = forms.DecimalField(max_digits=8, decimal_places=2, min_value=0)
