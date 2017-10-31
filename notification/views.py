from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect, Http404
from django.forms.formsets import formset_factory
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.contrib.syndication.views import Feed
import django.forms

import models
from .decorators import basic_auth_required, simple_basic_auth_callback
from .feeds import NoticeUserFeed

@basic_auth_required(realm='Notices Feed', callback_func=simple_basic_auth_callback)
def feed_for_user(request):
    url = "feed/%s" % request.user.username
    return Feed(request, url, {
        "feed": NoticeUserFeed,
    })

@login_required
def notices(request):
    initial = []
    for notice_type in models.NoticeType.objects.all():
        type_setting_initial = {}
        for medium, medium_label in models.NOTICE_MEDIA:
            try:
                type_setting_initial[medium] = models.NoticeSetting.objects.get(user=request.user,
                        notice_type=notice_type, medium=medium).send
            except models.NoticeSetting.DoesNotExist:
                type_setting_initial[medium] = False
        type_setting_initial['notice_type'] = notice_type
        initial.append(type_setting_initial)

    form_fields = dict([(medium_id, django.forms.BooleanField(label=medium_label, required=False)) \
                    for medium_id,medium_label in models.NOTICE_MEDIA])
    form_fields['notice_type'] = django.forms.ModelChoiceField(
                queryset=models.NoticeType.objects.all(), widget=django.forms.HiddenInput)
    form_class = type('NoticeForm', (django.forms.BaseForm,), {'base_fields': form_fields })
    formset_class = formset_factory(extra=0, form=form_class,
        can_order=False, can_delete=False, max_num=len(initial))
    formset = formset_class(data=request.POST or None, initial=initial)

    if request.method == "POST":
        if formset.is_valid():
            for form in formset.forms:
                cleaned_data = form.cleaned_data.copy()
                notice_type = cleaned_data.pop('notice_type')
                for medium_id, medium_label in models.NOTICE_MEDIA:
                    send = cleaned_data.get(medium_id, False)
                    ns, created = models.NoticeSetting.objects.get_or_create(user=request.user,
                            notice_type=notice_type, medium=medium_id,
                            defaults={'send': send})
                    if ns.send != send:
                        ns.send = send
                        ns.save()

    return render_to_response("notification/notices.html", {
        "formset": formset,
    }, context_instance=RequestContext(request))

@login_required
def single(request, id):
    notice = get_object_or_404(models.Notice, id=id)
    if request.user == notice.user:
        return render_to_response("notification/single.html", {
            "notice": notice,
        }, context_instance=RequestContext(request))
    raise Http404

@login_required
def archive(request, noticeid=None, next_page=None):
    if noticeid:
        try:
            notice = models.Notice.objects.get(id=noticeid)
            if request.user == notice.user or request.user.is_superuser:
                notice.archive()
            else:   # you can archive other users' notices
                    # only if you are superuser.
                return HttpResponseRedirect(next_page)
        except models.Notice.DoesNotExist:
            return HttpResponseRedirect(next_page)
    return HttpResponseRedirect(next_page)

@login_required
def delete(request, noticeid=None, next_page=None):
    if noticeid:
        try:
            notice = models.Notice.objects.get(id=noticeid)
            if request.user == notice.user or request.user.is_superuser:
                notice.delete()
            else:   # you can delete other users' notices
                    # only if you are superuser.
                return HttpResponseRedirect(next_page)
        except models.Notice.DoesNotExist:
            return HttpResponseRedirect(next_page)
    return HttpResponseRedirect(next_page)

@login_required
def mark_all_seen(request):
    for notice in models.Notice.objects.notices_for(request.user, unseen=True):
        notice.unseen = False
        notice.save()
    return HttpResponseRedirect(reverse("notification_notices"))
    
