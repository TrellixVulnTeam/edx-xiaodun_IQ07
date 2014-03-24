__author__ = 'lqr'
import logging
import urllib

from collections import defaultdict

from lxml import html

from django.conf import settings
from django.core.context_processors import csrf
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from edxmako.shortcuts import render_to_response, render_to_string
from django_future.csrf import ensure_csrf_cookie
from django.views.decorators.cache import cache_control
from django.db import transaction
from markupsafe import escape
import django.utils

from courseware import grades
from courseware.access import has_access
from courseware.courses import (get_courses, get_course_with_access, sort_by_announcement, get_course_info_section,
                                get_course_by_id, get_course, course_image_url, get_course_about_section, get_courses_by_search)

import courseware.tabs as tabs
from courseware.masquerade import setup_masquerade
from courseware.model_data import FieldDataCache
from .module_render import toc_for_course, get_module_for_descriptor
from courseware.models import StudentModule, StudentModuleHistory
from course_modes.models import CourseMode

from student.models import UserTestGroup, CourseEnrollment
from student.views import course_from_id, single_course_reverification_info
from util.cache import cache, cache_if_anonymous
from util.json_request import JsonResponse

from xblock.fragment import Fragment
from xmodule.modulestore import Location
from xmodule.modulestore.django import modulestore, loc_mapper
from xmodule.modulestore.exceptions import InvalidLocationError, ItemNotFoundError, NoPathToItem
from xmodule.modulestore.search import path_to_location
from xmodule.course_module import CourseDescriptor
from xmodule.contentstore.content import StaticContent
import shoppingcart

from microsite_configuration import microsite

log = logging.getLogger("edx.wechat")

template_imports = {'urllib': urllib}

def registered_for_course(course, user):
    """
    Return True if user is registered for course, else False
    """
    if user is None:
        return False
    if user.is_authenticated():
        return CourseEnrollment.is_enrolled(user, course.id)
    else:
        return False

def mobile_course_about(request, course_id):

    if microsite.get_value(
        'ENABLE_MKTG_SITE',
        settings.FEATURES.get('ENABLE_MKTG_SITE', False)
    ):
        raise Http404

    course = get_course_with_access(request.user, course_id, 'see_exists')
    registered = registered_for_course(course, request.user)

    if has_access(request.user, course, 'load'):
        course_target = reverse('mobi_info', args=[course.id])
    else:
        course_target = reverse('about_course', args=[course.id])

    show_courseware_link = (has_access(request.user, course, 'load') or
                            settings.FEATURES.get('ENABLE_LMS_MIGRATION'))

    # Note: this is a flow for payment for course registration, not the Verified Certificate flow.
    registration_price = 0
    in_cart = False
    reg_then_add_to_cart_link = ""
    if (settings.FEATURES.get('ENABLE_SHOPPING_CART') and
        settings.FEATURES.get('ENABLE_PAID_COURSE_REGISTRATION')):
        registration_price = CourseMode.min_course_price_for_currency(course_id,
                                                                      settings.PAID_COURSE_REGISTRATION_CURRENCY[0])
        if request.user.is_authenticated():
            cart = shoppingcart.models.Order.get_cart_for_user(request.user)
            in_cart = shoppingcart.models.PaidCourseRegistration.contained_in_order(cart, course_id)

        reg_then_add_to_cart_link = "{reg_url}?course_id={course_id}&enrollment_action=add_to_cart".format(
            reg_url=reverse('register_user'), course_id=course.id)

    # see if we have already filled up all allowed enrollments
    is_course_full = CourseEnrollment.is_course_full(course)

    return render_to_response('wechat/mobi_course_about.html',
                              {'course': course,
                               'registered': registered,
                               'course_target': course_target,
                               'registration_price': registration_price,
                               'in_cart': in_cart,
                               'reg_then_add_to_cart_link': reg_then_add_to_cart_link,
                               'show_courseware_link': show_courseware_link,
                               'is_course_full': is_course_full})
