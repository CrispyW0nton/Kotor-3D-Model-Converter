using System.Collections.ObjectModel;
using Avalonia.Controls.Models.TreeDataGrid;
using Avalonia.Controls;
using Kotor.NET.ResourceContainers;
using System.Linq;
using System.Security.AccessControl;
using DynamicData;
using Toolset.Controls;

namespace Toolset.ViewModels;

public class MainViewVM
{
    public IResourceContainer ActiveContainer { get; set; } = new Chitin(@"C:\Program Files (x86)\Steam\steamapps\common\swkotor");

    public MainViewVM()
    {

    }
}
