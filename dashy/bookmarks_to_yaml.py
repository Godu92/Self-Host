import yaml
from bs4 import BeautifulSoup


def parse_bookmarks(html_file: str) -> str:
    """Converts bookmarks html file into dashy yml list

    Args:
        html_file (str): the bookmarks file to convert to dashy list

    Returns:
        (str): a dashy styled yml list
    """
    with open(html_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    bookmarks: list[str] = []
    for bookmark in soup.find_all("a"):
        url: str = bookmark.get("href")
        title: str = bookmark.text.strip() or url
        target: str = bookmark.get("target", "newtab")

        bookmarks.append(
            {
                "title": title,
                "url": url,
                "target": target,
            }
        )

    return bookmarks


def main():
    """The main method"""
    html_file: str = "bookmarks.html"
    bookmarks: list[str] = parse_bookmarks(html_file)

    yaml_output: str = yaml.dump(bookmarks, default_flow_style=False)
    print(yaml_output)


if __name__ == "__main__":
    main()
