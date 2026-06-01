"""Load bakerydemo-equivalent blog content without external fixture files."""

from __future__ import annotations

import re

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import wagtail

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from django.core.files.images import get_image_dimensions
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from home.models import HomePage
from wagtail.images.models import Image
from wagtail.models import Collection, Site
from wagtail.rich_text import RichText
from wagtail.users.models import UserProfile

from blog.models import BlogIndexPage, BlogPage, Person


IMAGES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "fixtures"
    / "media"
    / "original_images"
)

COLLECTION_NAMES: dict[int, str] = {
    1: "Root",
    2: "Bakeries",
    3: "Other",
    4: "BreadPage Images",
    5: "Recipes",
}

IMG_BREADS4 = {
    "collection": 2,
    "title": "Rustic Country Loaf",
    "file": "original_images/breads4.jpg",
    "description": (
        "A loaf of bread resting on a rustic wooden table, showcasing its golden crust and "
        "inviting texture"
    ),
    "created_at": "2019-02-17T08:10:34.723Z",
    "uploaded_by_user": ["admin"],
}

IMG_BREAD5 = {
    "collection": 2,
    "title": "Golden Baguettes",
    "file": "original_images/bread5.jpg",
    "description": (
        "Two freshly baked loaves of bread resting on a wooden tray, showcasing their golden "
        "crusts and inviting aroma"
    ),
    "created_at": "2019-02-19T08:08:37.723Z",
    "uploaded_by_user": ["admin"],
}

IMG_BREAD6 = {
    "collection": 2,
    "title": "Artisan Boule",
    "file": "original_images/bread6.jpg",
    "description": (
        "A freshly baked loaf of bread resting on a cooling rack, showcasing its golden crust "
        "and inviting texture"
    ),
    "created_at": "2019-02-19T08:08:38.028Z",
    "uploaded_by_user": ["admin"],
}

IMG_SODA_BREAD = {
    "collection": 2,
    "title": "Soda Bread",
    "file": "original_images/soda_bread.jpg",
    "description": (
        "A piece of soda bread resting on a wooden table, showcasing its rustic texture and "
        "golden-brown crust"
    ),
    "created_at": "2019-02-21T08:10:30.772Z",
    "uploaded_by_user": ["admin"],
}

IMG_YEAST = {
    "collection": 2,
    "title": "Yeast",
    "file": "original_images/yeast.avif",
    "description": (
        "A close-up of small brown bits on a white surface, highlighting the texture and "
        "details of yeast extract"
    ),
    "created_at": "2019-02-21T07:50:10.793Z",
    "uploaded_by_user": ["admin"],
}

IMG_BEDOUINS = {
    "collection": 2,
    "title": "Bedouins",
    "file": "original_images/Bedouins_making_bread.jpg",
    "description": "Two Bedouin men sitting on the ground, skillfully making traditional bread",
    "created_at": "2019-02-21T07:59:50.671Z",
    "uploaded_by_user": ["admin"],
}

IMG_OLAND = {
    "collection": 2,
    "title": "Ølandshvedebrød",
    "file": "original_images/Olandshvedebrod_6082070226.jpg",
    "description": (
        "A loaf of Olandshvedebrod resting on a cooling rack, showcasing its golden crust and "
        "inviting texture"
    ),
    "created_at": "2019-02-21T08:05:08.529Z",
    "uploaded_by_user": ["admin"],
}

IMG_BREADS_MISC = {
    "collection": 4,
    "title": "Misc Breads",
    "file": "original_images/mixed_variety_of_traditional_european_sourdough_and_rye_round_bread_loaves.jpg",
    "description": (
        "A selection of various breads elegantly arranged on a table, showcasing different "
        "shapes and textures"
    ),
    "created_at": "2019-02-23T07:48:34.909Z",
    "uploaded_by_user": ["admin"],
}

IMG_RYE_WALNUT = {
    "collection": 4,
    "title": "Rye Bread",
    "file": "original_images/Sourdough_rye_with_walnuts.jpg",
    "description": "A loaf of sourdough rye with walnuts resting on a napkin atop a kitchen counter",
    "created_at": "2019-02-23T08:18:10.895Z",
    "uploaded_by_user": ["admin"],
    "focal_point_x": 519,
    "focal_point_y": 414,
}

IMG_BAKING_SODA = {
    "collection": 3,
    "title": "Baking Soda",
    "file": "original_images/bakingsoda.webp",
    "description": (
        "A bowl of baking soda with a wooden spoon resting on top, ready for use in baking or "
        "cooking"
    ),
    "created_at": "2019-03-22T06:13:09.773Z",
    "uploaded_by_user": ["admin"],
    "focal_point_x": 322,
    "focal_point_y": 319,
}

HOME_BODY = [
    {
        "type": "paragraph_block",
        "value": (
            '<p><b>Bread</b>\xa0is a\xa0<a href="https://en.wikipedia.org/wiki/Staple_food">staple '
            "food</a>\xa0prepared from a\xa0"
            '<a href="https://en.wikipedia.org/wiki/Dough">dough</a>\xa0of\xa0'
            '<a href="https://en.wikipedia.org/wiki/Flour">flour</a>\xa0and\xa0'
            '<a href="https://en.wikipedia.org/wiki/Water">water</a>, usually by\xa0'
            '<a href="https://en.wikipedia.org/wiki/Baking">baking</a>. Throughout recorded history '
            "it has been popular around the world and is one of the oldest artificial foods, having "
            "been of importance since the dawn of\xa0"
            '<a href="https://en.wikipedia.org/wiki/Agriculture#History">agriculture</a>.</p>'
            "<p>Proportions of types of flour and other ingredients vary widely, as do modes of "
            "preparation. As a result, types, shapes, sizes, and textures of breads differ around the "
            "world. Bread may be\xa0"
            '<a href="https://en.wikipedia.org/wiki/Leaven">leavened</a>\xa0by processes such as '
            "reliance on naturally occurring\xa0"
            '<a href="https://en.wikipedia.org/wiki/Sourdough">sourdough</a>\xa0microbes, chemicals, '
            "industrially produced yeast, or high-pressure aeration. Some bread is cooked before it "
            "can leaven, including for traditional or religious reasons. Non-cereal ingredients such "
            "as fruits, nuts and fats may be included. Commercial bread commonly contains additives to "
            "improve flavor, texture, color, shelf life, and ease of manufacturing.</p>"
        ),
        "id": "331ba9a8-8580-4bfb-b47f-73bb4ec40ec0",
    }
]

PERSONS = [
    {
        "pk": 1,
        "first_name": "Roberta",
        "last_name": "Johnson",
        "job_title": "Editorial Manager",
        "image": {
            "collection": 3,
            "title": "Roberta Johnson",
            "file": "original_images/roberta_johnson.jpeg",
            "description": "Roberta Johnson smiling with eyes closed near a plant with orange flowers",
            "created_at": "2019-02-17T07:43:46.304Z",
            "uploaded_by_user": ["admin"],
        },
    },
    {
        "pk": 2,
        "first_name": "Olivia",
        "last_name": "Ava",
        "job_title": "Director",
        "image": {
            "collection": 3,
            "title": "Olivia Ava",
            "file": "original_images/olivia_ava.jpeg",
            "description": (
                "A woman named Olivia Ava with a stylish afro hairstyle, radiating confidence and charm"
            ),
            "created_at": "2019-04-01T07:30:10.713Z",
            "uploaded_by_user": ["admin"],
        },
    },
    {
        "pk": 3,
        "first_name": "Lightnin'",
        "last_name": "Hopkins",
        "job_title": "Designer",
        "image": {
            "collection": 3,
            "title": "Lightnin' Hopkins",
            "file": "original_images/lightnin_hopkins.jpg",
            "description": "A black and white portrait of Lightnin' Hopkins",
            "created_at": "2019-04-01T07:31:21.251Z",
            "uploaded_by_user": ["admin"],
        },
    },
    {
        "pk": 4,
        "first_name": "Muddy",
        "last_name": "Waters",
        "job_title": "Assistant Editor",
        "image": {
            "collection": 3,
            "title": "Muddy Waters",
            "file": "original_images/muddy_waters_hUPkmSW.jpg",
            "description": (
                "A man named Muddy Waters wearing a stylish hat and a pair of sunglasses, smiling "
                "with his mouth open"
            ),
            "created_at": "2019-03-31T06:36:23.486Z",
            "uploaded_by_user": ["admin"],
        },
    },
]

POSTS: list[dict[str, Any]] = [
    {
        "slug": "wild-yeast",
        "title": "Tracking Wild Yeast",
        "subtitle": "The art of cultivating yeast",
        "introduction": (
            "Yeasts, with their single-celled growth habit, can be contrasted with molds, which grow "
            "hyphae. Fungal species that can take both forms (depending on temperature or other "
            'conditions) are called dimorphic fungi ("dimorphic" means "having two forms").'
        ),
        "image": IMG_YEAST,
        "body": [
            {
                "type": "paragraph_block",
                "value": '<p>Yeasts are eukaryotic, single-celled microorganisms classified as members of the fungus kingdom. The yeast lineage[which?] originated hundreds of millions of years ago, and 1,500 species are currently identified.[1][2][3] They are estimated to constitute 1% of all described fungal species.[4] Yeasts are unicellular organisms which evolved from multicellular ancestors,[5] with some species having the ability to develop multicellular characteristics by forming strings of connected budding cells known as pseudohyphae or false hyphae.[6] Yeast sizes vary greatly, depending on species and environment, typically measuring 3–4 µm in diameter, although some yeasts can grow to 40 µm in size.[7] Most yeasts reproduce asexually by mitosis, and many do so by the asymmetric division process known as budding.</p><h3>Contrast with Molds</h3><p>Yeasts, with their single-celled growth habit, can be contrasted with molds, which grow hyphae. Fungal species that can take both forms (depending on temperature or other conditions) are called dimorphic fungi ("dimorphic" means "having two forms").<br/></p><p>By fermentation, the yeast species Saccharomyces cerevisiae converts carbohydrates to carbon dioxide and alcohols – for thousands of years the carbon dioxide has been used in baking and the alcohol in alcoholic beverages.[8] It is also a centrally important model organism in modern cell biology research, and is one of the most thoroughly researched eukaryotic microorganisms. Researchers have used it to gather information about the biology of the eukaryotic cell and ultimately human biology.[9] Other species of yeasts, such as Candida albicans, are opportunistic pathogens and can cause infections in humans. Yeasts have recently been used to generate electricity in microbial fuel cells,[10] and produce ethanol for the biofuel industry.<br/></p><p>Yeasts do not form a single taxonomic or phylogenetic grouping. The term "yeast" is often taken as a synonym for Saccharomyces cerevisiae,[11] but the phylogenetic diversity of yeasts is shown by their placement in two separate phyla: the Ascomycota and the Basidiomycota. The budding yeasts ("true yeasts") are classified in the order Saccharomycetales,[12] within the phylum Ascomycota.<br/></p>',
                "id": "e015f74c-47d0-4631-b768-fa20e5ec1deb",
            },
            {
                "type": "image_block",
                "value": {
                    "image": IMG_RYE_WALNUT,
                    "caption": "Raised Yummy",
                    "attribution": "Creative Commons",
                },
                "id": "7e2a0b56-e8d7-46f1-920b-13a715dca209",
            },
        ],
        "date_published": "2019-01-12",
        "tags": ["yeast", "fermentation"],
        "author_person_pks": [1],
    },
    {
        "slug": "bread-circuses",
        "title": "Bread and Circuses",
        "subtitle": "The art of baking",
        "introduction": (
            "Baking is a method of cooking food that uses prolonged dry heat, normally in an oven, but "
            "also in hot ashes, or on hot stones. The most common baked item is bread but many other "
            "types of foods are baked."
        ),
        "image": IMG_BEDOUINS,
        "body": [
            {
                "type": "paragraph_block",
                "value": '<p data-block-key="gupgl">Heat is <b>gradually</b> transferred &quot;from the surface of cakes, cookies, and breads to their centre. As heat travels through it transforms batters and doughs into baked goods with a firm dry crust and a softer centre&quot;.[2] Baking can be combined with grilling to produce a hybrid barbecue variant by using both methods simultaneously, or one after the other. Baking is related to barbecuing because the concept of the masonry oven is similar to that of a smoke pit.</p>',
                "id": "03f86cc1-3c67-4b94-872e-af9ff708e4e6",
            },
            {
                "type": "image_block",
                "value": {
                    "image": IMG_SODA_BREAD,
                    "caption": "Soda Bread",
                    "attribution": "Creative Commons",
                },
                "id": "7518f81f-6654-438c-8a4d-f36b3f7c27c9",
            },
            {
                "type": "paragraph_block",
                "value": '<p data-block-key="yci2r">Because of historical social and familial roles,\xa0<a href="https://en.wikipedia.org/wiki/Baking">baking</a>\xa0has traditionally been performed at home by women for domestic consumption and by men in bakeries and restaurants for local consumption. When production was industrialized, baking was automated by machines in large factories. The art of baking remains a fundamental skill and is important for nutrition, as baked goods, especially breads, are a common but important food, both from an economic and cultural point of view. A person who crafts baked goods as a profession is called a baker.</p>',
                "id": "fed17107-0d58-45e5-8b80-58d1ba188045",
            },
            {
                "type": "image_block",
                "value": {
                    "image": IMG_BREADS4,
                    "caption": "Sourdough bread",
                    "attribution": "Creative Commons",
                },
                "id": "a3a480f6-d4e4-4f80-92c1-af97a9ee608d",
            },
        ],
        "date_published": "2019-02-14",
        "tags": ["yeast", "fire", "baking"],
        "author_person_pks": [2],
    },
    {
        "slug": "icelandic-baking",
        "title": "The Great Icelandic Baking Show",
        "subtitle": "Viking bakeries and Norse donuts",
        "introduction": (
            "Nordic bread culture has existed in Denmark, Finland, Norway, and Sweden from "
            "prehistoric time through to the present."
        ),
        "image": IMG_OLAND,
        "body": [
            {
                "type": "paragraph_block",
                "value": "<p>Four grain types dominated in the Nordic countries: barley and rye are the oldest; wheat and oats are more recent. During the Iron Age (500 AD – 1050 AD), rye became the most commonly used grain, followed by barley and oats. Rye was also the most commonly used grain for bread up until the beginning of the 20th century. Today, older grain types such as emmer and spelt are once again being cultivated and new bread types are being developed from these grains.</p><p>Archaeological finds in Denmark indicate use of the two triticum (wheat) species, emmer and einkorn, during the Mesolithic Period (8900 BC – 3900 BC). There is no direct evidence of bread-making, but cereals have been crushed, cooked and served as porridge since at least 4,200 BC. During the Neolithic Period (3900 BC – 1800 BC), when agriculture was introduced, barley seems to have taken over to some extent, and ceramic plates apparently used for baking are found. Moulded cereals, with water added to make a dough and baked or fried in the shape of bread, are known as burial gifts in Iron Age graves (200 AD onwards) in the Mälardalen area of central Sweden. However, it is not certain that this bread was eaten; it could just have been a burial gift. During the Bronze Age (1800 BC – 500 AD), oats and the triticum species spelt seem to have been the most commonly used grains, and we see the first real ovens, probably used for baking small loaves and perhaps the first bread (probably around 400 AD).</p><p><br/></p>",
                "id": "5a0af64d-01b0-4a7a-abc2-6ca6a7faab23",
            },
            {
                "type": "image_block",
                "value": {
                    "image": IMG_BAKING_SODA,
                    "caption": "Baking Soda",
                    "attribution": "Creative Commons",
                },
                "id": "103a747f-057a-4c95-9cbe-dfc57cf5107b",
            },
            {
                "type": "paragraph_block",
                "value": "<p>Scandinavian soldiers in Roman times apparently learned baking techniques when working as mercenaries in the Roman army (200–400 AD). They subsequently took the technique home with them to show that they had been employed in high status work on the continent[citation needed]. Early Christian traditions promoted an interest in bread. Culturally, German traditions have influenced most of the bread types in the Nordic countries. In the eastern part of Finland, there is a cultural link to Russia and Slavic bread traditions.</p><p>In the Nordic countries, bread was the main part of a meal until the late 18th century. Four different bread regions can be found in the Nordic area in the late 19th century. In the south, soft rye bread dominated. Further north came crisp bread, usually baked with rye, then thin and crispy barley bread. In the far north, soft barley loaves dominated. During the 19th century, potatoes began to become the centrepiece of meals and bread was put aside as an extra source of carbohydrates in a meal. Bread still retained its key function for breakfast, as the open sandwich is a starter for most Nordic people today and potatoes are used as a centrepiece in lunches and dinners.</p>",
                "id": "d327ccf8-308d-4145-9f1f-0bac66a36276",
            },
            {
                "type": "image_block",
                "value": {
                    "image": IMG_BREAD5,
                    "caption": "Fresh baked",
                    "attribution": "Creative Commons",
                },
                "id": "244a26d0-eae0-4799-8fad-ef0501bdfcff",
            },
            {
                "type": "paragraph_block",
                "value": "<p>A history of Nordic bread from around 1000 AD and some contemporary types and bread innovations is presented below. Countries are presented in alphabetic order (Denmark, Finland, Iceland, Norway and Sweden). The names of the bread types are mostly given in both the contemporary national language and in English.</p>",
                "id": "e0755385-6cf2-4b57-8612-17d5d29fadb6",
            },
        ],
        "date_published": "2019-03-21",
        "tags": ["grain", "fermentation"],
        "author_person_pks": [3],
    },
    {
        "slug": "joy-baking-soda",
        "title": "The Joy of (Baking) Soda",
        "subtitle": "The ingredients of traditional soda bread are flour, bread soda, salt, and buttermilk.",
        "introduction": (
            "During the early years of European settlement of the Americas, settlers and some groups of "
            "Indigenous peoples of the Americas used soda or pearl ash, more commonly known as potash "
            "(pot ash) or potassium carbonate, as a leavening agent (the forerunner to baking soda) in "
            "quick breads."
        ),
        "image": IMG_BAKING_SODA,
        "body": [
            {
                "type": "paragraph_block",
                "value": '<p>Since it has long been known and is widely used, the salt has many related names such as baking soda, bread soda, cooking soda, and bicarbonate of soda. In colloquial usage, the names sodium bicarbonate and bicarbonate of soda are often truncated. Forms such as sodium bicarb, bicarb soda, bicarbonate, bicarb, or even bica are common. The word saleratus, from Latin <i>sal æratus</i> meaning "aerated salt", was widely used in the 19th century for both sodium bicarbonate and potassium bicarbonate.</p>',
                "id": "dd7625bb-2b39-4729-a1e0-55c8f43473a4",
            },
            {
                "type": "image_block",
                "value": {
                    "image": IMG_BREAD6,
                    "caption": "Fresh baked",
                    "attribution": "Creative Commons",
                },
                "id": "200fa9e6-d5f2-493d-bbc2-df9bdaf731b7",
            },
            {
                "type": "paragraph_block",
                "value": '<p>The prefix, bi, in bicarbonate comes from an outdated naming system and is based on the observation that there is twice as much carbonate (CO3) per sodium in\xa0<a href="https://en.wikipedia.org/wiki/Sodium_bicarbonate">sodium bicarbonate</a>\xa0(NaHCO3) as there is carbonate per sodium in sodium carbonate (Na2CO3) and other carbonates. The modern way of analyzing the situation based on the exact chemical composition (which was unknown when the name sodium bicarbonate was coined) says this the other way around: there is half as much sodium in NaHCO3 as in Na2CO3 (Na versus Na2).</p>',
                "id": "f05234bc-2ad4-40cd-990b-36e1172b8129",
            },
            {
                "type": "image_block",
                "value": {
                    "image": IMG_BREADS_MISC,
                    "caption": "Cornucopia of Breads",
                    "attribution": "Creative Commons",
                },
                "id": "9d78ee98-13e7-44af-89c4-3a6ed989aaf3",
            },
        ],
        "date_published": "2019-02-08",
        "tags": ["grain", "soda", "yeast"],
        "author_person_pks": [3, 1],
    },
    {
        "slug": "sliced-bread",
        "title": "The Greatest Thing Since Sliced Bread",
        "subtitle": "Innovation in the brick oven",
        "introduction": (
            "Sandwich bread (also referred to as sandwich loaf)  is bread that is prepared specifically "
            "to be used for the preparation of sandwiches."
        ),
        "image": IMG_BREADS_MISC,
        "body": [
            {
                "type": "paragraph_block",
                "value": '<p>Sandwich breads are produced in many varieties, such as white, whole wheat, sourdough, rye, multigrain and others. Sandwich bread may be formulated to slice easily,[8] cleanly or uniformly, and may have a fine crumb (the soft, inner part of bread) and a light texture.[4] Sandwich bread may be designed to have a balanced proportion of crumb and crust, whereby the bread holds and supports fillings in place and reduces drips and messiness. <a href="https://en.wikipedia.org/wiki/Sandwich_bread">Some may be designed</a> to not become crumbly, hardened, dried or have too squishy a texture.</p>',
                "id": "6fbdf2bd-8994-40ed-b645-959e7dbf2d1e",
            },
            {
                "type": "block_quote",
                "value": {
                    "text": "Vegetables are a must on a diet. I suggest carrot cake, zucchini bread, and pumpkin pie.",
                    "attribute_name": "Jim Davis",
                },
                "id": "244030ba-e734-4c10-a819-4abac3dfdd21",
            },
            {
                "type": "image_block",
                "value": {
                    "image": {
                        "collection": 4,
                        "title": "Belgian Waffle",
                        "file": "original_images/Belgische_waffeln.jpg",
                        "description": (
                            "A Belgian waffle topped with fresh fruit and whipped cream, elegantly presented on a "
                            "black plate"
                        ),
                        "created_at": "2019-02-23T07:48:34.735Z",
                        "uploaded_by_user": ["admin"],
                    },
                    "caption": "Belgian Waffle",
                    "attribution": "Creative Commons",
                },
                "id": "9330b160-1111-4a25-b927-ec11a5fa10aa",
            },
            {
                "type": "paragraph_block",
                "value": '<p>Sandwich bread can refer to cross-sectionally square, sliced white and wheat bread, which has been described as "perfectly designed for holding square luncheon meat".[10] The bread used for preparing finger sandwiches is sometimes referred to as sandwich bread.[10] Pan de molde is a sandwich loaf.[11][12] Some sandwich breads are designed for use in the creation of specific types of sandwiches, such as the submarine sandwich.[13] For barbecuing, use of a high-quality white sandwich bread has been described as suitable for toasting over a fire.[14] Gluten-free sandwich bread may be prepared using gluten-free flour, teff flour.[15][16] and other ingredients.<br/></p><p>In the 1930s in the United States, the term sandwich loaf referred to sliced bread.[10] In contemporary times, U.S. consumers sometimes refer to white bread such as Wonder Bread as sandwich bread and sandwich loaf.[1] Wonder Bread produced and marketed a bread called Wonder Round sandwich bread, which was designed to be used with round-shaped cold cuts and other fillings such as eggs and hamburgers, but it was discontinued due to low consumer demand.[17] American sandwich breads have historically included some fat derived from the use of milk or oil to enrich the bread.</p>',
                "id": "ef3345bb-a75c-4723-8662-15b006dae55e",
            },
        ],
        "date_published": "2019-02-02",
        "tags": ["sandwich", "baking"],
        "author_person_pks": [1, 3],
    },
    {
        "slug": "desserts-benefits",
        "title": "Desserts with Benefits",
        "subtitle": "Banana toffee chocolate pie?",
        "introduction": (
            "A Boston cream pie is a yellow butter cake that is filled with custard or cream and topped "
            "with chocolate glaze."
        ),
        "image": {
            "collection": 3,
            "title": "Boston Cream Pie",
            "file": "original_images/bostoncream.png",
            "description": "A plate featuring three Boston Cream Pies, each adorned with rich chocolate frosting",
            "created_at": "2019-03-22T06:29:18.751Z",
            "uploaded_by_user": ["admin"],
            "focal_point_x": 465,
            "focal_point_y": 291,
            "focal_point_width": 923,
            "focal_point_height": 582,
        },
        "body": [
            {
                "type": "paragraph_block",
                "value": '<p data-block-key="2t5ek">Despite its name, it is in fact a cake, and not a pie.[2] The dessert acquired its name when cakes and pies were cooked in the same pans, and the words were used interchangeably.[3] In the latter part of the 19th century, this type of cake was variously called a &quot;cream pie&quot;, a &quot;chocolate cream pie&quot;, or a &quot;custard cake&quot;.[3]</p><p data-block-key="3lq30">Owners of the Parker House Hotel in Boston claim that the Boston cream pie was first created at the hotel by Armenian-French chef M. Sanzian in 1856.[4] Called a &quot;Chocolate Cream Pie&quot;, this cake consisted of two layers of French butter sponge cake filled with crème pâtissière and brushed with a rum syrup, its side coated with crème pâtissière overlain with toasted sliced almonds, and the top coated with chocolate fondant.[5] However, historians dispute this claim to primacy; while this cake may have been served then, there is no specific contemporaneous evidence of it, and custard-filled cake was already popular at that time.[3]</p>',
                "id": "b793eb57-cf99-4c2e-abc5-e3d5a8ea486b",
            },
            {
                "type": "image_block",
                "value": {
                    "image": IMG_BREAD6,
                    "caption": "Central Bakery",
                    "attribution": "Creative Commons",
                },
                "id": "556e76b0-0f5a-42bb-b039-653f3d6b1f0b",
            },
            {
                "type": "paragraph_block",
                "value": '<p data-block-key="lhqbi">The cake is likely derived from the Washington pie, a two-layer yellow cake filled with jam and topped with confectioner&#x27;s sugar, for which pastry cream of custard eventually replaced the jam, and a chocolate glaze replaced the confectioner&#x27;s sugar.[2] Today, the cake is topped with a chocolate glaze (such as ganache) and sometimes powdered sugar or a cherry.</p><p data-block-key="oauyc">The name first appeared in the 1872 Methodist Almanac.[3] Another early printed use of the term &quot;Boston cream pie&quot; occurred in the Granite Iron Ware Cook Book, printed in 1878.[2] The earliest known recipe of the modern variant was printed in Miss Parloa&#x27;s Kitchen Companion in 1887 as &quot;Chocolate Cream Pie&quot;.[2]</p><p data-block-key="11hv6">And on another note, here are cookies baking in the oven:</p><embed embedtype="media" url="https://www.youtube.com/watch?v=ofCHfv2lOTE"/><p data-block-key="dlchc"></p>',
                "id": "ac48af95-b3be-4602-8c2f-5c43fc080f17",
            },
        ],
        "date_published": "2019-02-24",
        "tags": ["dessert"],
        "author_person_pks": [2],
    },
]


def _dimensions_from_path(path: Path) -> tuple[int, int]:
    with path.open("rb") as fh:
        w, h = get_image_dimensions(fh)
    if w and h:
        return w, h
    if path.suffix.lower() == ".svg":
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'viewBox="0\s+0\s+([\d.]+)\s+([\d.]+)"', text)
        if m:
            return int(float(m.group(1))), int(float(m.group(2)))
    raise CommandError(f"Could not read dimensions for {path}")


def get_or_create_collection(pk: int) -> Collection:
    root = Collection.get_first_root_node()
    name = COLLECTION_NAMES.get(pk, f"Demo collection {pk}")
    existing = root.get_children().filter(name=name).first()
    if existing:
        return existing
    return root.add_child(name=name)


def _wagtail_image_from_spec(
    spec: dict[str, Any],
    *,
    cache: dict[str, Image],
    users_by_username: dict[str, AbstractUser],
    default_user: AbstractUser,
) -> Image:
    """
    Create Wagtail images from inlined dicts. Keys mirror bakerydemo fixture fields:
    collection, title, file, description, created_at, uploaded_by_user, focal_point_*.
    """
    cache_key = spec["file"]
    if cache_key in cache:
        return cache[cache_key]

    path = IMAGES_DIR / Path(spec["file"]).name
    if not path.is_file():
        raise CommandError(f"Missing image file: {path}")

    width, height = _dimensions_from_path(path)
    file_size = path.stat().st_size
    with path.open("rb") as fh:
        data = fh.read()
    django_file = ContentFile(data, name=path.name)

    collection = get_or_create_collection(spec["collection"])
    uploader = default_user
    for username in spec.get("uploaded_by_user") or []:
        if username in users_by_username:
            uploader = users_by_username[username]
            break

    img = Image(
        title=spec["title"],
        description=spec.get("description", ""),
        collection=collection,
        width=width,
        height=height,
        file_size=file_size,
        uploaded_by_user=uploader,
    )
    for key in (
        "focal_point_x",
        "focal_point_y",
        "focal_point_width",
        "focal_point_height",
    ):
        if key in spec and spec[key] is not None:
            setattr(img, key, spec[key])

    img.file.save(path.name, django_file, save=False)
    img.save()

    Image.objects.filter(pk=img.pk).update(
        created_at=parse_datetime(spec["created_at"])
    )

    cache[cache_key] = img
    return img


def _blocks_to_stream(
    blocks: list[dict[str, Any]],
    *,
    load_image: Callable[[dict[str, Any]], Image],
) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for block in blocks:
        btype = block["type"]
        value = block["value"]
        if btype == "paragraph_block":
            out.append((btype, RichText(value)))
        elif btype == "package_callout":
            if not isinstance(value, dict):
                raise CommandError("package_callout must have a dict value")
            out.append(
                (
                    btype,
                    {
                        "title": value["title"],
                        "body": RichText(value["body"]),
                    },
                )
            )
        elif btype == "image_block":
            if not isinstance(value, dict) or "image" not in value:
                raise CommandError("image_block must have value.image as a dict")
            image_spec = value["image"]
            if not isinstance(image_spec, dict):
                raise CommandError("image_block value.image must be a dict")
            img = load_image(image_spec)
            out.append(
                (
                    btype,
                    {
                        "image": img,
                        "caption": value.get("caption", ""),
                        "attribution": value.get("attribution", ""),
                    },
                )
            )
        elif btype == "block_quote":
            out.append(
                (
                    btype,
                    value
                    if "settings" in value
                    else {
                        **value,
                        "settings": {"theme": "default", "text_size": "default"},
                    },
                )
            )
        else:
            raise ValueError(f"Unsupported block type {btype!r} in demo loader")
    return out


class Command(BaseCommand):
    help = (
        "Create demo content from inlined bakerydemo blog data: homepage, blog index, "
        "posts, author snippets, and an admin user (idempotent where possible)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recreate blog pages and demo user even if they already exist.",
        )

    def handle(self, *args, **options):
        force = options["force"]

        site = Site.objects.get(is_default_site=True)
        home = HomePage.objects.live().first()
        if not home:
            raise CommandError("No live HomePage found. Run migrations first.")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
                "first_name": "Admin",
                "last_name": "Example",
            },
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password("changeme")
        user.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Admin user 'admin' / 'changeme' "
                f"({'created' if created else 'updated, password reset'})."
            )
        )

        UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "theme": "light",
                "dismissibles": {
                    "help": True,
                    f"whats-new-in-wagtail-{wagtail.VERSION[0]}.{wagtail.VERSION[1]}": True,
                    "editor-guide": True,
                },
            },
        )

        users_by_username: dict[str, AbstractUser] = {user.username: user}
        for u in User.objects.exclude(pk=user.pk).filter(
            username__in=["german", "arabic"]
        ):
            users_by_username[u.username] = u

        feature_cache: dict[str, Image] = {}

        def load_image(spec: dict[str, Any]) -> Image:
            return _wagtail_image_from_spec(
                spec,
                cache=feature_cache,
                users_by_username=users_by_username,
                default_user=user,
            )

        existing_index = (
            BlogIndexPage.objects.child_of(home).filter(slug="blog").first()
        )
        if existing_index and not force:
            blog_index = existing_index
            self.stdout.write("Blog index already exists; skipping blog tree creation.")
        else:
            if existing_index and force:
                existing_index.delete()
            blog_index = BlogIndexPage(
                title="Blog",
                slug="blog",
                seo_title="Wagtail Bakeries Blog",
                introduction="Welcome to our blog",
                image=load_image(
                    {
                        "collection": 2,
                        "title": "Seeded Harvest Loaf",
                        "file": "original_images/breads3.jpg",
                        "description": "High-angle close-up view of a rectangular granola bar resting on a sheet of brown parchment paper, which is itself laid over a white linen cloth with thin red stripes",
                        "created_at": "2019-02-17T08:10:34.580Z",
                        "uploaded_by_user": ["admin"],
                    }
                ),
                show_in_menus=True,
            )
            home.add_child(instance=blog_index)
            blog_index.save_revision().publish()

            person_by_pk: dict[int, Person] = {}
            for pdata in PERSONS:
                author_img = load_image(pdata["image"])
                p = Person(
                    first_name=pdata["first_name"],
                    last_name=pdata["last_name"],
                    job_title=pdata["job_title"],
                    image=author_img,
                )
                p.save()
                p.save_revision().publish()
                person_by_pk[pdata["pk"]] = p

            for spec in POSTS:
                bp = BlogPage(
                    title=spec["title"],
                    slug=spec["slug"],
                    subtitle=spec["subtitle"],
                    introduction=spec["introduction"],
                    image=load_image(spec["image"]),
                    body=_blocks_to_stream(
                        spec["body"],
                        load_image=load_image,
                    ),
                    date_published=date.fromisoformat(spec["date_published"]),
                )
                blog_index.add_child(instance=bp)
                for person_pk in spec["author_person_pks"]:
                    bp.blog_person_relationship.create(person=person_by_pk[person_pk])
                for tag_name in spec["tags"]:
                    bp.tags.add(tag_name)
                bp.save_revision().publish()

            self.stdout.write(
                self.style.SUCCESS("Created blog index and bakerydemo sample posts.")
            )

        home.hero_text = "A sample demo site"
        home.hero_cta = "Learn more about Wagtail"
        home.hero_cta_link = blog_index
        home.image = load_image(
            {
                "collection": 2,
                "title": "Dark Rye Sourdough",
                "file": "original_images/breads1.jpg",
                "description": "Brown bread with powdered sugar sprinkled on top",
                "width": 1080,
                "height": 831,
                "created_at": "2019-02-17T08:10:34.237Z",
                "uploaded_by_user": ["admin"],
            }
        )
        home.featured_section_3_title = "Blog"
        home.featured_section_3 = blog_index
        home.body = _blocks_to_stream(HOME_BODY, load_image=load_image)
        home.save_revision().publish()

        site.site_name = site.site_name or "Demo"
        site.save()

        self.stdout.write(
            self.style.SUCCESS("Homepage updated with hero and blog section.")
        )
