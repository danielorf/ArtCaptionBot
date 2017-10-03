from artcaptionbot import ArtCaptionBot

ab3k = ArtCaptionBot('ArtCaptionBot', '_config.ini')
print(len(ab3k.history_id_set))
print(ab3k.is_explicit)
print(ab3k.caption)
print(ab3k.post_to_twitter())