using System.Collections.ObjectModel;
using MapBuilder.Data;

namespace MapBuilder.ViewModels;

public class MainViewModel : ViewModelBase
{
    public ObservableCollection<Placement> Placements { get; }

    public MainViewModel(MapData mapData)
    {
        Placements = new ObservableCollection<Placement>(mapData.Placements);
    }
}
