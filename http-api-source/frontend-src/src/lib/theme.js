import { createTheme } from 'thememirror';
import { tags } from '@lezer/highlight';

export const quixTheme = createTheme({
    variant: 'dark',
    settings: {
        background: '#1e1e35',
        foreground: '#ffffff',
        caret: '#00d26a',
        selection: '#3d396666',
        lineHighlight: '#252542',
        gutterBackground: '#13131f',
        gutterForeground: '#6b6b80',
    },
    styles: [
        { tag: tags.string, color: '#00d26a' },
        { tag: tags.number, color: '#ffa502' },
        { tag: tags.bool, color: '#ff6b81' },
        { tag: tags.null, color: '#ff6b81' },
        { tag: tags.propertyName, color: '#a0a0b8' },
        { tag: tags.brace, color: '#b57edc' },
        { tag: tags.squareBracket, color: '#5bc0de' },
        { tag: tags.separator, color: '#6b6b80' },
        { tag: tags.punctuation, color: '#6b6b80' },
    ],
});
