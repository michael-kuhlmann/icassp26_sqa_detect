# Adding Audio Files to GitHub Pages

## Quick Setup Guide

1. **Add your audio files**: Place your audio files (MP3, WAV, OGG, M4A) in the `audio/` directory
2. **Update the index.html** (optional): You can customize the display by editing the JavaScript in `index.html`
3. **Commit and push**: The GitHub Pages site will automatically update

## Example: Adding Audio Files

### Option 1: Simple File Addition
Just add your audio files to the `audio/` directory and they will be accessible via direct links.

### Option 2: Dynamic List (Requires Manual Update)
To display a nice list with descriptions, update the `audioFiles` array in `index.html`:

```javascript
const audioFiles = [
    {
        name: 'Sample Audio 1',
        filename: 'audio/sample1.mp3',
        description: 'Description of the first audio file'
    },
    {
        name: 'Sample Audio 2', 
        filename: 'audio/sample2.wav',
        description: 'Description of the second audio file'
    }
];
```

## Repository Structure
```
/
├── index.html              # Main page template
├── audio/                  # Directory for audio files
│   ├── README.md          # Instructions for audio files
│   └── [your-audio-files] # Place your audio files here
├── .github/workflows/
│   └── deploy-pages.yml   # GitHub Actions deployment
└── README.md              # This file
```

## GitHub Pages URL
Once set up, your site will be available at:
`https://michael-kuhlmann.github.io/icassp26_sqa_detect/`

## Automatic Deployment
The site is automatically deployed when you push changes to the main branch via GitHub Actions.