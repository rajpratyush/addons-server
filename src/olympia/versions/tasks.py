from __future__ import division
import operator
import os
import itertools

from django.template import loader

import olympia.core.logger

from olympia import amo
from olympia.amo.celery import task
from olympia.amo.decorators import use_primary_db
from olympia.amo.utils import extract_colors_from_image, pngcrush_image
from olympia.devhub.tasks import resize_image
from olympia.files.models import File
from olympia.files.utils import get_background_images
from olympia.versions.models import Version, VersionPreview

from .utils import (
    AdditionalBackground,
    process_color_value,
    encode_header,
    write_svg_to_png,
)


log = olympia.core.logger.getLogger('z.versions.task')


def _build_static_theme_preview_context(theme_manifest, file_):
    # First build the context shared by both the main preview and the thumb
    context = {'amo': amo}
    context.update(
        dict(
            process_color_value(prop, color)
            for prop, color in theme_manifest.get('colors', {}).items()
        )
    )
    images_dict = theme_manifest.get('images', {})
    header_url = images_dict.get('theme_frame', images_dict.get('headerURL', ''))
    file_ext = os.path.splitext(header_url)[1]
    backgrounds = get_background_images(file_, theme_manifest)
    header_src, header_width, header_height = encode_header(
        backgrounds.get(header_url), file_ext
    )
    context.update(
        header_src=header_src,
        header_src_height=header_height,
        header_width=header_width,
    )
    # Limit the srcs rendered to 15 to ameliorate DOSing somewhat.
    # https://bugzilla.mozilla.org/show_bug.cgi?id=1435191 for background.
    additional_srcs = images_dict.get('additional_backgrounds', [])[:15]
    additional_alignments = theme_manifest.get('properties', {}).get(
        'additional_backgrounds_alignment', []
    )
    additional_tiling = theme_manifest.get('properties', {}).get(
        'additional_backgrounds_tiling', []
    )
    additional_backgrounds = [
        AdditionalBackground(path, alignment, tiling, backgrounds.get(path))
        for (path, alignment, tiling) in itertools.zip_longest(
            additional_srcs, additional_alignments, additional_tiling
        )
        if path is not None
    ]
    context.update(additional_backgrounds=additional_backgrounds)
    return context


@task
@use_primary_db
def generate_static_theme_preview(theme_manifest, version_pk):
    # Make sure we import `index_addons` late in the game to avoid having
    # a "copy" of it here that won't get mocked by our ESTestCase
    from olympia.addons.tasks import index_addons

    tmpl = loader.get_template('devhub/addons/includes/static_theme_preview_svg.xml')
    file_ = File.objects.filter(version_id=version_pk).first()
    if not file_:
        return
    context = _build_static_theme_preview_context(theme_manifest, file_)
    renderings = sorted(
        amo.THEME_PREVIEW_RENDERINGS.values(), key=operator.itemgetter('position')
    )
    colors = None
    for rendering in renderings:
        # Create a Preview for this size.
        preview = VersionPreview.objects.create(
            version_id=version_pk,
            position=rendering['position'],
            sizes={'thumbnail_format': rendering['thumbnail_format']},
        )
        # Add the size to the context and render
        context.update(svg_render_size=rendering['full'])
        svg = tmpl.render(context).encode('utf-8')
        if write_svg_to_png(svg, preview.image_path):
            resize_image(
                preview.image_path,
                preview.thumbnail_path,
                rendering['thumbnail'],
                format=rendering['thumbnail_format'],
            )
            pngcrush_image(preview.image_path)
            # Extract colors once and store it for all previews.
            # Use the thumbnail for extra speed, we don't need to be super accurate.
            if colors is None:
                colors = extract_colors_from_image(preview.thumbnail_path)
            data = {
                'sizes': {
                    'image': rendering['full'],
                    'thumbnail': rendering['thumbnail'],
                    'thumbnail_format': rendering['thumbnail_format'],
                },
                'colors': colors,
            }
            preview.update(**data)
    addon_id = Version.objects.values_list('addon_id', flat=True).get(id=version_pk)
    index_addons.delay([addon_id])


@task
def delete_preview_files(pk, **kw):
    VersionPreview.delete_preview_files(
        sender=None, instance=VersionPreview.objects.get(pk=pk)
    )
