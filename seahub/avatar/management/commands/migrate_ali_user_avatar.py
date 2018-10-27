import logging
import urllib2

from django.core.files import File
from django.core.management.base import BaseCommand

from seahub.alibaba.models import AlibabaProfile
from seahub.avatar.models import Avatar

# Get an instance of a logger
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Migrate avatars from Alibaba profile to database."
    label = "avatar_migrate_ali_user_avatar"

    def add_arguments(self, parser):
        parser.add_argument(
            '-c', '--count', default=10, type=int,
        )

    def handle(self, *args, **options):
        self.cnt = options['count']

        self.do_action()

    def _save_avatar(self, username, pic):
        logger.info("start to retrieve pic from %s" % pic)

        filedata = urllib2.urlopen(pic)
        datatowrite = filedata.read()
        filename = '/tmp/%s.jpg' % username
        with open(filename, 'wb') as f:
            f.write(datatowrite)

        logger.info("save pic to %s" % filename)
        avatar = Avatar(emailuser=username, primary=True)
        avatar.avatar.save(
            'image.jpg', File(open(filename))
        )
        avatar.save()

    def do_action(self):
        '''
        SELECT `alibaba_profile`.`id`, `alibaba_profile`.`uid`, `alibaba_profile`.`personal_photo_url` FROM `alibaba_profile` WHERE (`alibaba_profile`.`work_status` = A AND NOT (`alibaba_profile`.`uid` IN (SELECT U0.`emailuser` AS Col1 FROM `avatar_avatar` U0))) LIMIT 100
        '''
        qs = AlibabaProfile.objects.filter(work_status='A').values('id', 'uid', 'personal_photo_url').exclude(uid__in=Avatar.objects.all().values_list('emailuser', flat=True))[:self.cnt]

        logger.info('Start migrating ..., total count [%d]' % self.cnt)

        success = 0
        for e in qs:
            pic = e['personal_photo_url']
            if not pic:
                return

            self._save_avatar(e['uid'], pic)
            success += 1

        logger.info('Finish migrating [%d] avatars\n' % success)
