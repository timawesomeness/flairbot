import praw
import prawcore
import json
import re
import time
import config

reddit = praw.Reddit(username=config.username, password=config.password, client_id=config.client_id, client_secret=config.client_secret, user_agent=config.user_agent)

# Get posts, check flair, check age, check if already logged, if not logged and meets requirements, send PM, log PM and post
# Get PMs, check if response to logged PM, check if contains valid flair, if yes flair and unlog, if no message back error
# Check logged posts, if post is flaired unlog, if post is >10min old remove and unlog

# Constants
SUBREDDIT = config.subreddit    # sub without /r/
MAX_TIME = 600                  # time for removal in seconds
PM_TIME = 60                    # time for manual flairing before PM
LOG_FILENAME = "log.json"       # filename of file for keeping track of work
CSS_CLASSES = {"meme": "meme",  # CSS classes for flairs
               "social":       "social",
               "advice":       "advice",
               "serious":      "serious",
               "discussion":   "discuss",
               "other":        "other",
               "rant":         "rant",
               "relationship": "relationship",
               "media":        "media"}

log = {}

def load_log():
    global log
    with open(LOG_FILENAME) as f:
        log = json.load(f)

def log_item(post_id, message_id):
    log[post_id] = message_id
    try:
        with open(LOG_FILENAME, "w") as f:
            json.dump(log, f)
    except IOError:
        print("Error writing file.")

def remove_item(post_id):
    del log[post_id]
    try:
        with open(LOG_FILENAME, "w") as f:
            json.dump(log, f)
    except IOError:
        print("Error writing file.")

def check_log(post_id):
    return (post_id in log)

def get_post_from_message(message_id):
    for post, data in log.items():
        if data == message_id:
            return post
    return None

def check_new_posts():
    for post in reddit.subreddit(SUBREDDIT).new(limit=100): # get 100 most recent posts
        if (not post.link_flair_text) and (time.time() - post.created_utc > PM_TIME) and (time.time() - post.created_utc <= MAX_TIME) and (not check_log(post.name)): # if post isn't flaired, is old enough, and isn't logged, send PM
            post.author.message("Please flair your post!", f"[Your recent post]({post.shortlink}) does not have any flair and will soon be removed.\n\nPlease add flair to your post. If you do not add flair within **10 minutes**, you will have to resubmit your post.\n\nDon't know how to flair your post? Click [here](http://imgur.com/a/GmrnD) to view this helpful guide on how to flair your post.\n\nYou may also reply to this message with a flair that you would like assigned to your post. The following replies are accepted:\n\n* Meme\n* Social\n* Advice\n* Serious\n* Discussion\n* Other\n* Rant\n* Relationship\n* Media")
            time.sleep(0.5)                                         # make sure reddit's had time to update the inbox because...
            message = [_ for _ in reddit.inbox.sent(limit=1)][0]    # of this stupid hack because /api/compose doesn't return any information about the sent message
            if post.shortlink in message.body:
                log_item(post.name, message.name) # log sent PM 
            else: 
                raise Exception("grrrrrrrrrrrrr")

def check_new_messages():
    for message in reddit.inbox.unread(limit=None): # get unread PMs                                                                            
        if isinstance(message, praw.models.Message): # make sure PM is a PM                                                                         
            post_id = get_post_from_message(message.first_message_name) # get the post corresponding to the message thread                                                                 
            if post_id:                                                                                                                     
                flair = re.search(r"meme|social|advice|serious|discussion|other|rant|relationship|media", message.body, flags=re.I) # check for a flair in the received PM
                if flair:
                    flair = flair[0]
                    try:
                        post = reddit.submission(id=post_id[3:]) 
                        post.mod.flair(text=flair.title(), css_class=CSS_CLASSES[flair.lower()]) # flair the post - assuming flairs should be title case
                    except prawcore.exceptions.Forbidden as e:
                        print("we don't have permission to flair here. not a mod?")
                    except (praw.exceptions.PRAWException, prawcore.PrawcoreException) as e:
                        raise e
                    else:
                        remove_item(post_id) # remove from log
                else:
                    message.reply(f"Unfortunately, '{message.body}' does not contain a valid flair.") # send PM on error
        message.mark_read()

def check_logged_posts():
    if len(log) > 0:
        for post in reddit.info(list(log)): # iterate through the log, check if posts are still valid
            if (not post) or (post.author is None): # if the post is deleted or somehow doesn't exist
                remove_item(post.name)
            elif post.link_flair_text: # if the post is flaired
                remove_item(post.name)
            elif time.time() - post.created_utc > MAX_TIME: # if the post is too old
                try:
                    post.mod.remove() # remove post from sub
                except prawcore.exceptions.Forbidden as e:
                    print("we don't have permission to remove here. not a mod?")
                except (praw.exceptions.PRAWException, prawcore.PrawcoreException) as e:
                    raise e
                else:
                    post.author.message("Your post has been removed as you did not flair it in time.", f"[Your recent post]({post.shortlink}) was not flaired in the given time and has been removed. It will not be approved, please resubmit your post and remember to flair it once it is posted.")
                remove_item(post.name)

if __name__ == "__main__":
    try:
        load_log()
    except:
        pass # log probably doesn't exist yet
    while True:
        try:
            check_new_posts()
        except (praw.exceptions.PRAWException, prawcore.PrawcoreException) as e:
            print(f"Error connecting to reddit: {str(e)}")
            time.sleep(5)
        except Exception as e:
            print(f"This should never happen. {str(e)}")

        try:
            check_new_messages()
        except (praw.exceptions.PRAWException, prawcore.PrawcoreException) as e:
            print(f"Error connecting to reddit: {str(e)}")
            time.sleep(5)

        try:
            check_logged_posts()
        except (praw.exceptions.PRAWException, prawcore.PrawcoreException) as e:
            print(f"Error connecting to reddit: {str(e)}")
            time.sleep(5)
        time.sleep(5)

