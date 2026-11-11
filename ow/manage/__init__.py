"""Per-type adapters for tracked customizations."""

from ow.manage.automations import Automations
from ow.manage.code import Functions, Tools
from ow.manage.models import Models
from ow.manage.prompts import Prompts
from ow.manage.skills import Skills

ADAPTERS = {
    adapter.type: adapter
    for adapter in (Functions(), Tools(), Models(), Prompts(), Skills(), Automations())
}
