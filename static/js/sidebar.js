$(document).ready(function () {
    $('#sidebarCollapse').on('click', function () {
        $('.sidebar').toggleClass('active');
    });

    // Dropdown-Menü-Funktionalität
    $('.dropdown-toggle').on('click', function () {
        $(this).next('.collapse').slideToggle();
    });
}); 