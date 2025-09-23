# LoquiLex UI Flows

## 2. Storage Setup Flow

### Overview
The storage setup flow ensures users configure a valid storage location for their transcription outputs before proceeding to model selection and session creation.

### Flow Steps

1. **Storage Step** (`/`)
   - Display current storage location information
   - Show disk usage statistics (total, free, used, percentage)
   - Validate storage location is writable
   - Allow user to change storage location
   - Validate new storage paths
   - Continue to Model Selection

2. **Model Selection** (`/models`)
   - Select ASR and MT models
   - Configure session parameters
   - Start transcription session

3. **Session View** (`/session/:sessionId`)
   - Live transcription interface
   - Real-time translation display

### Storage Step Details

#### Current Storage Display
- **Path**: Shows the current base directory path
- **Disk Usage**: 
  - Total space available on the disk
  - Free space remaining
  - Used space percentage with color coding:
    - Green: <75% used
    - Yellow: 75-90% used
    - Red: >90% used
- **Status**: Writable/Not writable indicator

#### Path Validation
- Validates absolute paths only
- Creates directory if it doesn't exist
- Checks write permissions
- Warns if less than 1GB free space
- Updates settings when valid path is set

#### Navigation
- **Continue to Model Selection**: Proceeds to `/models` when storage is valid
- **Refresh Storage Info**: Reloads current storage statistics

### Storage Requirements
- Minimum 1GB free space recommended
- Directory must be writable
- Audio files (if enabled) require additional space
- Transcription files are typically small (~1KB per minute)

### Error Handling
- Invalid paths show validation messages
- Permission errors are clearly displayed
- Network errors during validation are handled gracefully
- Storage info refresh failures show user-friendly errors

### State Management
- Storage location is persisted in localStorage via settings
- Changes to baseDir trigger app restart notification (future enhancement)
- Settings are automatically saved when valid path is set

### API Endpoints Used
- `GET /storage/info?path={path}` - Get storage statistics
- `POST /storage/base-directory` - Validate and set base directory

### User Experience
- Clean, intuitive interface following existing design patterns
- Real-time feedback during path validation
- Visual indicators for storage status and usage
- Progressive disclosure of advanced options