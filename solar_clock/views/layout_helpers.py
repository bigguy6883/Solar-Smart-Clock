"""Layout helper utilities for consistent positioning and spacing."""

from typing import Tuple


class LayoutHelpers:
    """Utility class for common layout calculations."""

    @staticmethod
    def calculate_centered_x(total_width: int, element_width: int) -> int:
        """
        Calculate X position to center an element horizontally.

        Args:
            total_width: Total available width
            element_width: Width of element to center

        Returns:
            X position for left edge of centered element
        """
        return (total_width - element_width) // 2

    @staticmethod
    def calculate_two_column_layout(
        width: int, margin: int = 10, gap: int = 10
    ) -> Tuple[int, int, int]:
        """
        Calculate positions for a two-column layout.

        Args:
            width: Total available width
            margin: Margin from edges
            gap: Gap between columns

        Returns:
            Tuple of (col1_x, col2_x, col_width)
        """
        available_width = width - (2 * margin) - gap
        col_width = available_width // 2
        col1_x = margin
        col2_x = margin + col_width + gap
        return (col1_x, col2_x, col_width)

    @staticmethod
    def calculate_three_column_layout(
        width: int, margin: int = 10, gap: int = 10
    ) -> Tuple[int, int, int, int]:
        """
        Calculate positions for a three-column layout.

        Args:
            width: Total available width
            margin: Margin from edges
            gap: Gap between columns

        Returns:
            Tuple of (col1_x, col2_x, col3_x, col_width)
        """
        available_width = width - (2 * margin) - (2 * gap)
        col_width = available_width // 3
        col1_x = margin
        col2_x = margin + col_width + gap
        col3_x = margin + (2 * col_width) + (2 * gap)
        return (col1_x, col2_x, col3_x, col_width)

    @staticmethod
    def distribute_boxes_horizontal(
        width: int, count: int, box_width: int, margin: int = 10
    ) -> list[int]:
        """
        Distribute boxes evenly across horizontal space.

        Args:
            width: Total available width
            count: Number of boxes
            box_width: Width of each box
            margin: Margin from edges

        Returns:
            List of X positions for each box
        """
        if count == 0:
            return []
        if count == 1:
            return [LayoutHelpers.calculate_centered_x(width, box_width)]

        # Calculate available space and gaps
        available_width = width - (2 * margin)
        total_box_width = count * box_width
        total_gap = available_width - total_box_width
        gap = total_gap // (count - 1) if count > 1 else 0

        # Calculate positions
        positions = []
        x = margin
        for i in range(count):
            positions.append(x)
            x += box_width + gap

        return positions

    @staticmethod
    def calculate_vertical_stack(
        start_y: int, heights: list[int], spacing: int = 10
    ) -> list[int]:
        """
        Calculate Y positions for vertically stacked elements.

        Args:
            start_y: Starting Y position
            heights: List of heights for each element
            spacing: Spacing between elements

        Returns:
            List of Y positions for each element
        """
        positions = []
        y = start_y
        for height in heights:
            positions.append(y)
            y += height + spacing
        return positions

    @staticmethod
    def fit_text_in_width(
        text: str, max_width: int, truncate_suffix: str = "..."
    ) -> str:
        """
        Truncate text to fit within a maximum width.

        Note: This is a simple character-based truncation.
        For pixel-perfect truncation, use PIL's textbbox with actual font.

        Args:
            text: Text to truncate
            max_width: Maximum character count
            truncate_suffix: Suffix to add when truncating

        Returns:
            Truncated text
        """
        if len(text) <= max_width:
            return text
        return text[: max_width - len(truncate_suffix)] + truncate_suffix

    @staticmethod
    def calculate_grid_positions(
        width: int,
        height: int,
        rows: int,
        cols: int,
        cell_width: int,
        cell_height: int,
        margin: int = 10,
    ) -> list[Tuple[int, int]]:
        """
        Calculate positions for a grid layout.

        Args:
            width: Total available width
            height: Total available height
            rows: Number of rows
            cols: Number of columns
            cell_width: Width of each cell
            cell_height: Height of each cell
            margin: Margin from edges

        Returns:
            List of (x, y) tuples for each grid cell (row-major order)
        """
        positions = []

        # Calculate spacing
        total_grid_width = cols * cell_width
        total_grid_height = rows * cell_height

        available_width = width - (2 * margin)
        available_height = height - (2 * margin)

        h_gap = (available_width - total_grid_width) // (cols + 1) if cols > 1 else 0
        v_gap = (available_height - total_grid_height) // (rows + 1) if rows > 1 else 0

        # Calculate starting position
        start_x = margin + h_gap
        start_y = margin + v_gap

        # Generate positions
        for row in range(rows):
            for col in range(cols):
                x = start_x + col * (cell_width + h_gap)
                y = start_y + row * (cell_height + v_gap)
                positions.append((x, y))

        return positions
