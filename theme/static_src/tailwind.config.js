/**
 * This is a minimal config.
 *
 * If you need the full config, get it from here:
 * https://unpkg.com/browse/tailwindcss@latest/stubs/defaultConfig.stub.js
 */

module.exports = {
    content: [
        /**
         * HTML. Paths to Django template files that will contain Tailwind CSS classes.
         */

        /*  Templates within theme app (<tailwind_app_name>/templates), e.g. base.html. */
        '../templates/**/*.html',

        /*
         * Main templates directory of the project (BASE_DIR/templates).
         * Adjust the following line to match your project structure.
         */
        '../../templates/**/*.html',

        /*
         * Templates in other django apps (BASE_DIR/<any_app_name>/templates).
         * Adjust the following line to match your project structure.
         */
        '../../**/templates/**/*.html',

        /**
         * JS: If you use Tailwind CSS in JavaScript, uncomment the following lines and make sure
         * patterns match your project structure.
         */
        /* JS 1: Ignore any JavaScript in node_modules folder. */
        // '!../../**/node_modules',
        /* JS 2: Process all JavaScript files in the project. */
        // '../../**/*.js',

        /**
         * Python: If you use Tailwind CSS classes in Python, uncomment the following line
         * and make sure the pattern below matches your project structure.
         */
        // '../../**/*.py'
    ],
    theme: {
        extend: {
            colors: {
                /* Design system HAZON — tokens únicos de cor (S2 do PRD). */
                hazon: {
                    night: '#0b2029',      /* fundo base */
                    abyss: '#072026',      /* header / superfícies mais escuras */
                    deep: '#0e3a44',       /* gradiente de fundo */
                    surface: '#0d2a33',    /* superfícies escuras (cartões sólidos) */
                    mid: '#112530',        /* gradiente de fundo */
                    primary: '#0b6f74',
                    'primary-dark': '#075b60',
                    accent: '#74b3c6',
                    text: '#f4fafb',
                    muted: '#bcd3da',
                    dim: '#6f8a93',
                    success: '#7fe3c4',
                    'success-bright': '#4ade80',
                    warn: '#fbbf24',
                    danger: '#fca5a5',
                    info: '#c084fc',
                    orange: '#fb923c',
                    blue: '#60a5fa',
                    slate: '#94a3b8',
                    pink: '#f472b6',
                },
            },
            fontFamily: {
                sans: ['Manrope', 'Segoe UI', 'sans-serif'],
                display: ['Fraunces', 'Georgia', 'serif'],
            },
            boxShadow: {
                'glow-accent': '0 0 8px rgba(116,179,198,0.44)',
                'glow-warn': '0 0 8px rgba(251,191,36,0.44)',
                'accent-lg': '0 10px 30px -12px rgba(116,179,198,0.35)',
                soft: '0 8px 30px -12px rgba(0,0,0,0.40)',
            },
        },
    },
    plugins: [
        /**
         * '@tailwindcss/forms' is the forms plugin that provides a minimal styling
         * for forms. If you don't like it or have own styling for forms,
         * comment the line below to disable '@tailwindcss/forms'.
         */
        require('@tailwindcss/forms'),
        require('@tailwindcss/typography'),
        require('@tailwindcss/aspect-ratio'),
    ],
}
