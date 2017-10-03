import praw, requests, twython, urllib, random, configparser, time


class ArtCaptionBot(object):
    '''
    A bot that gathers images from reddit, captions them with Microsoft Computer Vision API, and tweets the image and
    caption along with some metadata.

    Attributes:
        twitter_handle:     string; twitter handle to tweet result
        subreddit_list:     list of strings: list of subreddits to gather images from
        filter_explicit:    bool:  If true, used to filter out images deemed explicit by Microsoft Computer Vision API
    '''

    def __init__(self, twitter_handle, config_file, subreddit_list=['itookapicture', 'albumartporn', 'photocritique'],
                 filter_explicit=True):

        self.config = configparser.ConfigParser()
        self.config.read(config_file, encoding='utf8')
        self.ignore_list = []

        self.twitter_handle = twitter_handle
        self.subreddit_list = subreddit_list
        self.filter_explicit = filter_explicit
        self.history_id_set = self.get_twitter_post_history(post_count=50)
        while self.history_id_set == -1:
            print('Retrying Twitter history retrieval')
            time.sleep(60)
            self.history_id_set = self.get_twitter_post_history(post_count=50)

        self.reddit_post = self.get_reddit_post()
        while self.reddit_post == -1:
            print('Retrying reddit post retrieval')
            time.sleep(60)
            self.reddit_post = self.get_reddit_post()

        self.image_url = self.reddit_post[2]
        self.caption_dict = self.get_caption()
        while (self.caption_dict == -1) or ('code' in self.caption_dict):
            print('Post failed, post ID added to ignored list')
            print('Ignored post list: ')
            print(self.ignore_list)
            self.ignore_list.append(self.reddit_post[0])
            self.reddit_post = self.get_reddit_post()
            self.image_url = self.reddit_post[2]
            self.caption_dict = self.get_caption()

        self.is_explicit = self.caption_dict["adult"]["isAdultContent"]

        while filter_explicit and self.caption_dict['adult']['isAdultContent']:
            print('Explicit post detected, post ID added to ignored list')
            print('Ignored post list: ')
            print(self.ignore_list)
            self.ignore_list.append(self.reddit_post[0])
            self.reddit_post = self.get_reddit_post()
            self.image_url = self.reddit_post[2]
            self.caption_dict = self.get_caption()

        self.caption = '\'' + self.caption_dict["description"]["captions"][0][
            'text'] + '\'' + '\n' + self.__get_certainty(
            self.caption_dict["description"]["captions"][0]['confidence']) + ' - ' + str(
            round(float(self.caption_dict["description"]["captions"][0]['confidence']) * 100)) + '%' + '\n' + \
                       self.reddit_post[3]


    def get_twitter_post_history(self, post_count=50):
        '''
        Gets the most recent Twitter posts (default of 50) and extracts the reddit post ids.

        :param post_count:  int; Max number of Twitter posts to retrieve
        :return:    set of Strings; Collection of reddit post ids found in the most recent Twitter posts
        '''
        try:
            twitter = twython.Twython(
                app_key=self.config['twitter']['application_key'],
                app_secret=self.config['twitter']['application_secret'],
                oauth_token=self.config['twitter']['oauth_token'],
                oauth_token_secret=self.config['twitter']['oauth_token_secret']
            )

            tweets = twitter.get_user_timeline(screen_name=self.twitter_handle, count=post_count)

            history_ids = set()
            for tweet in tweets:
                try:
                    history_ids.add(tweet['entities']['urls'][0]['display_url'].split('/')[-1])
                except:
                    continue

            return history_ids

        except Exception as e:
            print('Error retrieving Twitter history: ')
            print(e)
            return -1

    def get_reddit_post(self, submission_limit=50):
        '''
        Gets a list of reddit posts, checks for dupicates and allowed formats, return information about first passing
        post.

        :param post_history:        set of strings; Collection of reddit post ids used to prevent duplicate posting
        :param submission_limit:    int; Maximum number of reddit posts to retrieve
        :return:                    tuple; reddit post (id, title, url, shortlink)
        '''
        allowed_formats = ['jpg', 'jpeg', 'png', 'gif', 'bmp']
        subreddit = self.subreddit_list[random.randint(0, len(self.subreddit_list) - 1)]

        try:
            reddit = praw.Reddit(client_id=self.config['reddit']['client_id'],
                                 client_secret=self.config['reddit']['client_secret'],
                                 user_agent=self.config['reddit']['user_agent'],
                                 username=self.config['reddit']['username'],
                                 password=self.config['reddit']['password']
                                 )

            for submission in reddit.subreddit(subreddit).hot(limit=submission_limit):
                if (submission.id in self.history_id_set) or (submission.id in self.ignore_list):
                    continue
                else:
                    if (submission.url.split('.')[-1] in allowed_formats):
                        return (submission.id, submission.title, submission.url, submission.shortlink)
                    else:
                        continue

            return -1

        except Exception as e:
            print('Error:')
            print(e)
            print('Reddit request failed, post ID added to ignored list')
            print(self.ignore_list)
            self.ignore_list.append(self.reddit_post[0])
            # self.reddit_post = self.get_reddit_post()
            return -1

    def get_caption(self):
        '''

        :return:            dict: caption response dict, contains caption and metadata
        '''
        subscription_key = 'c7000990ecf2460ba58c17c5586a205b'
        uri_base = 'https://westus.api.cognitive.microsoft.com'

        headers = {
            # Request headers.
            'Content-Type': 'application/json',
            'Ocp-Apim-Subscription-Key': subscription_key,
        }

        params = {
            'visualFeatures': 'Categories,Description,Color,Adult',
            'language': 'en',
        }

        body = "{'url':'" + self.image_url + "'}"

        try:
            response = requests.post(uri_base + '/vision/v1.0/analyze', data=body, headers=headers,
                                     params=params)
            parsed = response.json()

            return parsed

        except Exception as e:
            print('Error:')
            print(e)
            print('Captioning failed, post ID added to ignored list')
            print('Ignored post list: ')
            print(self.ignore_list)
            self.ignore_list.append(self.reddit_post[0])
            # self.reddit_post = self.get_reddit_post()
            # self.image_url = self.reddit_post[2]
            # self.caption_dict = self.get_caption()
            return -1

    @staticmethod
    def __get_certainty(confidence):
        conf_score = float(confidence)
        if conf_score > 0.9:
            return 'Very Sure'
        elif conf_score > 0.75:
            return 'Kinda Sure'
        elif conf_score > 0.5:
            return 'Somewhat Sure'
        else:
            return 'Not Sure'

    def post_to_twitter(self):
        twitter = twython.Twython(
            app_key=self.config['twitter']['application_key'],
            app_secret=self.config['twitter']['application_secret'],
            oauth_token=self.config['twitter']['oauth_token'],
            oauth_token_secret=self.config['twitter']['oauth_token_secret']
        )

        try:
            f = urllib.request.urlopen(self.image_url)
            response = twitter.upload_media(media=f)
            status_details = twitter.update_status(status=self.caption, media_ids=[response['media_id']])
            return status_details
        except:
            print('Error:')
            print(e)
            print('Twitter posting failed, post ID added to ignored list')
            print('Ignored post list: ')
            print(self.ignore_list)
            self.ignore_list.append(self.reddit_post[0])
            self.reddit_post = self.get_reddit_post()
            self.image_url = self.reddit_post[2]
            self.caption_dict = self.get_caption()
            self.post_to_twitter()
