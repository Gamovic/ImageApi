# ImageApi
Get, Post and Delete images

GET all example (json):

{
    "id": "35b44b29-37cb-419a-b1a3-3e8f062cc4c6",
    "filename": "arrow.png",
    "url": "/images/arrow.png",
    "source": "project",
    "dimensions": {
      "width": 512,
      "height": 512
    },
    "format": "PNG",
    "mode": "RGBA",
    "size_bytes": 5501,
    "size_kb": 5.37
  }


GET id example:
{
  "id": "35b44b29-37cb-419a-b1a3-3e8f062cc4c6"
}


POST example:
{
  file: (image file)
  "filename": "string.png"
