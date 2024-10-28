import yaml
from bs4 import BeautifulSoup

def parse_bookmarks(html_file):
    with open(html_file, 'r') as f:
        soup = BeautifulSoup(f, 'html.parser')

    bookmarks = []
    for bookmark in soup.find_all('a'):
        url = bookmark.get('href')
        title = bookmark.text.strip() or url
        target = bookmark.get('target','newtab')  # default to'self' if not specified
        # id = bookmark.get('id')

        bookmarks.append({
            'title': title,
            'url': url,
            'target': target,
            # 'id': id
        })

    return bookmarks

def main():
    html_file = 'bookmarks.html'
    bookmarks = parse_bookmarks(html_file)

    yaml_output = yaml.dump(bookmarks, default_flow_style=False)
    print(yaml_output)

if __name__ == '__main__':
    main()