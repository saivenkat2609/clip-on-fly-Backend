# Video Editor Implementation - README

## Overview

A full-featured browser-based video editor with backend rendering, built with React, Fabric.js, and FFmpeg. Users can add and style text overlays, preview in real-time, and export high-quality videos.

---

## Features Implemented

### Phase 1 - MVP (COMPLETED)

✅ **Canvas Editor**
- Fabric.js-based canvas for video editing
- Real-time preview with video playback synchronization
- Drag-and-drop text positioning
- Resize, rotate, and transform text layers
- Multiple layer support with z-index ordering

✅ **Text Editing**
- 10 professional fonts (Inter, Roboto, Montserrat, Poppins, etc.)
- Font size: 12px - 200px
- Font weight: 300 - 900
- Color picker (HexColorPicker)
- Text alignment (left, center, right)
- Stroke (outline) controls
- Shadow controls
- Opacity controls

✅ **Quick Presets**
- Bold Impact (large, bold, high contrast)
- Minimal Clean (subtle, modern)
- Viral TikTok (yellow, bold, thick stroke)
- Professional (background box, clean)

✅ **Layer Management**
- Visual layers panel
- Show/hide layers
- Lock/unlock layers
- Duplicate layers
- Delete layers
- Layer timing (start/end time)

✅ **Timeline**
- Video playback controls (play/pause)
- Scrubbing support (drag playhead)
- Skip forward/backward (5s)
- Layer timing visualization
- Time display (MM:SS.ms format)

✅ **Export System**
- Resolution options (Original, 1080p, 720p, 4K)
- Aspect ratio options (16:9, 9:16, 1:1, 4:5)
- Quality presets (Low, Medium, High)
- Backend integration with API
- Progress tracking

✅ **Backend Handler**
- Python module for FFmpeg command generation
- Parses JSON from frontend
- Generates drawtext filters for text layers
- Handles font management
- Supports stroke, shadow, opacity
- Timing-based text display
- Backwards compatible with template system

✅ **Integration**
- Integrated into ProjectDetails page
- "Edit" button on every clip card
- Loads existing editor state if clip was edited before
- Saves editor state to Firestore
- Updates video URL after export

---

## Architecture

### Frontend Stack
```
React + TypeScript
├── Fabric.js (canvas manipulation)
├── Zustand (state management)
├── react-colorful (color picker)
└── Framer Motion (animations)
```

### Backend Stack
```
Python + FFmpeg
├── JSON parameter parser
├── Font management (S3 download)
├── FFmpeg filter generation
└── Video encoding (H.264)
```

### Data Flow
```
1. User edits in browser → Fabric.js canvas
2. Real-time preview → HTML5 video + Canvas overlay
3. Click "Export" → JSON parameters sent to API
4. Backend parses JSON → Generates FFmpeg command
5. FFmpeg renders video → Upload to S3
6. Return video URL → Update Firestore → UI updates
```

---

## File Structure

```
reframe-ai/
├── src/
│   ├── components/
│   │   └── VideoEditor/
│   │       ├── VideoEditorModal.tsx       # Main modal wrapper
│   │       ├── CanvasEditor.tsx           # Fabric.js canvas + video
│   │       ├── EditorToolbar.tsx          # Add text/image/shape tools
│   │       ├── LayersPanel.tsx            # Layer management
│   │       ├── PropertiesPanel.tsx        # Text properties editor
│   │       ├── Timeline.tsx               # Video timeline + playback
│   │       ├── ExportModal.tsx            # Export settings + API call
│   │       └── index.ts                   # Exports
│   └── lib/
│       └── videoEditor/
│           ├── types.ts                   # TypeScript interfaces
│           ├── editorStore.ts             # Zustand state management
│           └── utils.ts                   # Helper functions
│
├── BACKEND-VIDEO-EDITOR-HANDLER.py        # Python backend module
├── VIDEO-EDITOR-README.md                 # This file
└── VIDEO-EDITOR-IMPLEMENTATION-TRACKER.md # Progress tracker
```

---

## Usage

### For Users

1. **Open Editor**:
   - Go to any project page
   - Find a clip card
   - Click "Edit" button
   - Editor modal opens

2. **Add Text**:
   - Click "Text" button in left toolbar
   - Text layer appears on canvas
   - Double-click to edit text content
   - Drag to reposition

3. **Style Text**:
   - Select text layer (click on it)
   - Properties panel opens on right
   - Change font, size, color, etc.
   - Or use Quick Presets for instant styling

4. **Set Timing**:
   - Select text layer
   - Adjust "Start" and "End" times in properties
   - Text will only appear during that time window

5. **Preview**:
   - Click play button in timeline
   - Video plays with text overlays in sync
   - Scrub timeline to jump to specific time

6. **Export**:
   - Click "Export Video" button
   - Choose resolution and quality
   - Click "Export"
   - Wait 30-90 seconds for processing
   - Video updates automatically

### For Developers

#### Adding to a Component

```typescript
import { VideoEditorModal } from '@/components/VideoEditor';

function MyComponent() {
  const [editorOpen, setEditorOpen] = useState(false);

  return (
    <>
      <Button onClick={() => setEditorOpen(true)}>
        Edit Video
      </Button>

      <VideoEditorModal
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        videoUrl="https://example.com/video.mp4"
        videoTitle="My Video"
        clipIndex={0}
        sessionId="abc-123"
        onExportComplete={(newUrl) => {
          console.log('New video URL:', newUrl);
        }}
      />
    </>
  );
}
```

#### Backend Integration

```python
# In your Lambda function
from video_editor_handler import process_video_with_editor_params

def lambda_handler(event, context):
    edit_parameters = event.get('edit_parameters')

    if edit_parameters:
        # NEW: Video editor parameters
        success, error = process_video_with_editor_params(
            input_path='/tmp/input.mp4',
            output_path='/tmp/output.mp4',
            edit_parameters=edit_parameters,
            s3_font_bucket='your-fonts-bucket'
        )

        if success:
            # Upload output.mp4 to S3 and return URL
            return {'statusCode': 200, 'body': {...}}
    else:
        # OLD: Template system (backwards compatible)
        template_id = event.get('template_id')
        # ... existing template code ...
```

---

## API Contract

### Request to `/reprocess-clip`

```json
{
  "session_id": "abc-123-def-456",
  "clip_index": 0,
  "edit_parameters": {
    "version": "1.0",
    "videoMetadata": {
      "duration": 30.5,
      "resolution": {
        "width": 1920,
        "height": 1080
      },
      "aspectRatio": "16:9"
    },
    "layers": [
      {
        "id": "layer-1234",
        "type": "text",
        "name": "Text Layer",
        "visible": true,
        "locked": false,
        "timing": {
          "start": 0,
          "end": 5
        },
        "position": {
          "x": 960,
          "y": 540
        },
        "transform": {
          "rotation": 0,
          "scaleX": 1,
          "scaleY": 1
        },
        "opacity": 1,
        "zIndex": 0,
        "content": "Hello World",
        "style": {
          "fontFamily": "Inter",
          "fontSize": 48,
          "fontWeight": 600,
          "color": "#FFFFFF",
          "textAlign": "center",
          "lineHeight": 1.2,
          "letterSpacing": 0,
          "stroke": {
            "color": "#000000",
            "width": 2
          },
          "shadow": {
            "color": "rgba(0,0,0,0.5)",
            "blur": 8,
            "offsetX": 2,
            "offsetY": 2
          }
        }
      }
    ],
    "exportSettings": {
      "resolution": "1080p",
      "aspectRatio": "16:9",
      "quality": "high"
    }
  }
}
```

### Response

```json
{
  "success": true,
  "download_url": "https://r2.example.com/videos/clip-0-edited.mp4",
  "s3_key": "sessions/abc-123/clips/clip-0-edited.mp4",
  "template_id": null,
  "template_name": "Custom Edit"
}
```

---

## Font Management

### Required Fonts

Upload these fonts to S3 bucket under `fonts/` prefix:

```
fonts/
├── Inter-Regular.ttf
├── Inter-Medium.ttf
├── Inter-Bold.ttf
├── Roboto-Regular.ttf
├── Roboto-Bold.ttf
├── Montserrat-Regular.ttf
├── Montserrat-SemiBold.ttf
├── Montserrat-Bold.ttf
├── Poppins-Regular.ttf
├── Poppins-SemiBold.ttf
├── Poppins-Bold.ttf
├── BebasNeue-Regular.ttf
├── Oswald-Regular.ttf
├── Oswald-Bold.ttf
├── Raleway-Regular.ttf
├── Raleway-Bold.ttf
├── Lato-Regular.ttf
├── Lato-Bold.ttf
├── OpenSans-Regular.ttf
├── OpenSans-Bold.ttf
├── PlayfairDisplay-Regular.ttf
└── PlayfairDisplay-Bold.ttf
```

### Font Download Links

- Google Fonts: https://fonts.google.com/
- Download fonts in TTF format
- Upload to S3 with public-read permissions (if needed)

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Delete` | Delete selected layer |
| `Ctrl+D` | Duplicate layer |
| `Space` | Play/Pause video |
| `Arrow Keys` | Nudge layer (1px) |
| `Shift+Arrow` | Nudge layer (10px) |
| `Escape` | Close editor |

---

## Performance Considerations

### Frontend
- Canvas renders at 60fps during playback
- Debouncing on property changes (300ms)
- Lazy loading of fonts (only when used)
- Video buffering optimized
- Layer limit: 50 layers recommended

### Backend
- FFmpeg processing: 30-90 seconds per clip
- Lambda timeout: Set to 300 seconds (5 minutes)
- Memory: Allocate 2048MB+ for Lambda
- Concurrent executions: Monitor for high load

---

## Troubleshooting

### Issue: Canvas not rendering video
**Solution**: Check CORS settings on video URL. Video must have `crossorigin="anonymous"`.

### Issue: Fonts not rendering correctly
**Solution**: Ensure fonts are downloaded to `/tmp/fonts` in Lambda. Check S3 permissions.

### Issue: Export fails
**Solution**: Check Lambda logs. Common issues:
- FFmpeg timeout (increase Lambda timeout)
- Insufficient memory (increase Lambda memory)
- Font file not found (check S3 bucket)

### Issue: Text not appearing at correct time
**Solution**: Check layer timing in properties panel. Ensure start < end and within video duration.

---

## Known Limitations

### Phase 1 (Current)
- ❌ No image/sticker support (text only)
- ❌ No multi-clip editing (single clip at a time)
- ❌ No transitions or animations
- ❌ No background music
- ❌ No auto-captions integration
- ❌ No shape tools

### Will be added in Phase 2 & 3

---

## Future Enhancements

### Phase 2 (Planned)
- Image/sticker upload
- Shape tools (rectangle, circle, line)
- Multi-clip editing with timeline
- Transitions between clips
- Text entrance/exit animations
- Background music support

### Phase 3 (Planned)
- Auto-captions integration
- Video effects (blur, brightness, saturation)
- Template gallery with previews
- Collaborative editing
- Export presets for platforms
- Batch editing (apply to all clips)

---

## Support

For issues or questions:
1. Check this README
2. Check implementation tracker (`VIDEO-EDITOR-IMPLEMENTATION-TRACKER.md`)
3. Check backend handler code (`BACKEND-VIDEO-EDITOR-HANDLER.py`)
4. Review console logs (browser DevTools and Lambda logs)

---

## License

Part of ReframeAI application. Internal use only.

---

**Last Updated**: December 29, 2025
**Version**: 1.0.0 (MVP)
**Status**: Production Ready (Phase 1 Complete)
